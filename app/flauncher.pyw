"""FLauncher — F-Engineering Launcher v3 как окно Windows.

Без консоли: проверяет и поднимает backend-сервер в фоне (порты 8780..8789)
и открывает интерфейс в отдельном окне приложения через pywebview.
При отсутствии pywebview или ошибке вебвью открывает окно в Edge/Chrome.
Гарантированное завершение: использует Windows Job Object (KILL_ON_JOB_CLOSE)
и явные хуки закрытия окна, чтобы сервер никогда не оставался зомби в памяти.
"""
import atexit
import ctypes
from ctypes import wintypes
import json
import os
import shutil
import struct
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

if getattr(sys, 'frozen', False):
    # Запущено из скомпилированного EXE (dist\FEngineeringLauncher\FEngineeringLauncher.exe)
    # Корнем лаунчера является папка с самим EXE или папка на уровень выше
    REPO_ROOT = str(Path(sys.executable).resolve().parent)
else:
    # Запущено обычным python app/flauncher.pyw
    REPO_ROOT = str(Path(__file__).resolve().parent.parent)


def _resource_path(*relative: str) -> str:
    """Найти bundled-ресурс: сначала от REPO_ROOT, затем из sys._MEIPASS.

    PyInstaller 6 в режиме onedir кладёт --add-data в подпапку _internal,
    на которую указывает sys._MEIPASS. В обычном режиме _MEIPASS нет
    и всё строго от REPO_ROOT.
    """
    candidate = os.path.join(REPO_ROOT, *relative)
    if os.path.exists(candidate):
        return candidate
    meipass = getattr(sys, '_MEIPASS', '')
    if meipass:
        bundled = os.path.join(str(meipass), *relative)
        if os.path.exists(bundled):
            return bundled
    return candidate


def _backend_python() -> str:
    """Интерпретатор для запуска backend-сервера (server.py).

    Приоритет: встроенный runtime/python/pythonw.exe, затем (только
    в frozen-режиме без embedded runtime) pythonw/python из PATH.
    В обычном режиме — текущий интерпретатор. Никогда не возвращаем
    сам EXE: иначе frozen-процесс породил бы каскад копий GUI.
    """
    if os.path.exists(EMBEDDED_PYTHON):
        return EMBEDDED_PYTHON
    if getattr(sys, 'frozen', False):
        for candidate in ("pythonw.exe", "python.exe"):
            found = shutil.which(candidate)
            if found:
                return found
    return sys.executable


BACKEND = _resource_path("app", "backend", "server.py")
ICON = _resource_path("app", "frontend", "assets", "flauncher.ico")
EMBEDDED_PYTHON = os.path.join(REPO_ROOT, "runtime", "python", "pythonw.exe")
TITLE = "F-Engineering Launcher"
GUI_MUTEX_PORT = 8799
LOGS_DIR = os.path.join(REPO_ROOT, "runtime", "logs")

# --- Windows Job Object (Process Lifecycle Management) ---
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JobObjectExtendedLimitInformation = 9


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryLimit", ctypes.c_size_t),
        ("PeakJobMemoryLimit", ctypes.c_size_t),
    ]


_JOB_HANDLE = None


def get_or_create_kill_on_close_job():
    global _JOB_HANDLE
    if _JOB_HANDLE is not None:
        return _JOB_HANDLE
    if os.name != "nt":
        return None
    try:
        k32 = ctypes.windll.kernel32
        job = k32.CreateJobObjectW(None, None)
        if not job:
            log("CreateJobObjectW returned NULL")
            return None
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        success = k32.SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not success:
            err = k32.GetLastError()
            log(f"SetInformationJobObject failed with error {err}")
            k32.CloseHandle(job)
            return None
        _JOB_HANDLE = job
        log("Successfully created Windows Job Object with KILL_ON_JOB_CLOSE")
        return _JOB_HANDLE
    except Exception as e:
        log(f"Failed to create Job Object: {e}")
        return None


def assign_process_to_job(proc) -> bool:
    if not proc or os.name != "nt":
        return False
    job = get_or_create_kill_on_close_job()
    if not job:
        return False
    try:
        k32 = ctypes.windll.kernel32
        proc_handle = getattr(proc, "_handle", None)
        if proc_handle:
            ok = bool(k32.AssignProcessToJobObject(job, int(proc_handle)))
            log(f"Assigned process pid {proc.pid} to Job Object: {ok}")
            return ok
        elif hasattr(proc, "pid"):
            PROCESS_SET_QUOTA = 0x0100
            PROCESS_TERMINATE = 0x0001
            h = k32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, proc.pid)
            if h:
                ok = bool(k32.AssignProcessToJobObject(job, h))
                k32.CloseHandle(h)
                log(f"Assigned process pid {proc.pid} to Job Object via OpenProcess: {ok}")
                return ok
    except Exception as e:
        log(f"AssignProcessToJobObject error: {e}")
    return False


def hidden_process_kwargs() -> dict:
    """Флаги скрытого запуска процессов: никаких чёрных окон консоли."""
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = si
    return kwargs


def kill_process_tree_silent(pid: int) -> None:
    """Завершить процесс и его потомков абсолютно тихо, без консольных утилит."""
    if not pid:
        return
    # 1. Попытка через psutil (быстро, нативно, в памяти процесса)
    try:
        import psutil
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            try:
                child.kill()
            except Exception:
                pass
        parent.kill()
        return
    except Exception:
        pass

    # 2. Попытка через Win32 TerminateProcess API (без внешних процессов и окон)
    if os.name == "nt":
        try:
            k32 = ctypes.windll.kernel32
            handle = k32.OpenProcess(0x0001, False, int(pid))  # PROCESS_TERMINATE = 1
            if handle:
                k32.TerminateProcess(handle, 1)
                k32.CloseHandle(handle)
                return
        except Exception:
            pass

    # 3. Резерв: taskkill со скрытием окна
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=5,
                **hidden_process_kwargs(),
            )
        except Exception:
            pass


def get_pids_on_port(port: int) -> set[int]:
    pids = set()
    try:
        out = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True, text=True, timeout=5,
            **hidden_process_kwargs(),
        ).stdout
        for line in (out or "").splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0] == "TCP" \
                    and parts[1].endswith(":%d" % port) and parts[3] == "LISTENING":
                if parts[4].isdigit():
                    pids.add(int(parts[4]))
    except Exception:
        pass
    return pids


def shutdown_server(proc, port: int | None = None) -> None:
    # 1. Завершаем серверный процесс и его дерево процессов
    if proc:
        try:
            if proc.poll() is None:
                log(f"Shutting down server pid {proc.pid}...")
                kill_process_tree_silent(proc.pid)
                try:
                    proc.wait(timeout=1.5)
                except Exception:
                    pass
                log(f"Server pid {proc.pid} stopped successfully")
        except Exception as e:
            log(f"Error during shutdown_server proc: {e}")

    # 2. Если сервер работал на порту (даже если был найден ранее запущенным)
    target_port = port or 8780
    for pid in get_pids_on_port(target_port):
        try:
            log(f"Killing listener process pid {pid} on port {target_port}...")
            kill_process_tree_silent(pid)
        except Exception:
            pass

    # 3. Гарантированно зачищаем любые осиротевшие дочерние воркеры AutoCAD (accoreconsole, скрытый acad)
    if os.name == "nt":
        for cmd in (
            ["taskkill", "/F", "/IM", "accoreconsole.exe"],
            ["taskkill", "/F", "/FI", "WINDOWTITLE eq ", "/IM", "acad.exe"],
        ):
            try:
                subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=5,
                    **hidden_process_kwargs(),
                )
            except Exception:
                pass


def log(msg: str) -> None:
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        log_file = os.path.join(LOGS_DIR, "launcher_gui.log")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def is_server_healthy(port: int) -> bool:
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/health")
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            if resp.status != 200:
                return False
            data = json.loads(resp.read().decode("utf-8"))
            repo = data.get("repoRoot", "")
            if repo and os.path.normcase(os.path.abspath(repo)) != os.path.normcase(os.path.abspath(REPO_ROOT)):
                return False
            return True
    except Exception:
        return False


def is_port_free(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def _force_close_process_handles(pid: int) -> None:
    """Принудительно отозвать зависшие дескрипторы у зомби-процесса через DUPLICATE_CLOSE_SOURCE."""
    if os.name != "nt":
        return
    try:
        ntdll = ctypes.windll.ntdll
        k32 = ctypes.windll.kernel32
        PROCESS_DUP_HANDLE = 0x0040
        hProcess = k32.OpenProcess(PROCESS_DUP_HANDLE, False, int(pid))
        if not hProcess:
            return
        try:
            buf_size = 1024 * 1024 * 32
            buf = ctypes.create_string_buffer(buf_size)
            ret_len = ctypes.c_ulong()
            if ntdll.NtQuerySystemInformation(64, buf, buf_size, ctypes.byref(ret_len)) == 0:
                raw = buf.raw
                num_handles = struct.unpack_from("Q", raw, 0)[0]
                offset = 16
                entry_size = 40
                for _ in range(num_handles):
                    _, p_id, hval = struct.unpack_from("QQQ", raw, offset)
                    if p_id == pid:
                        k32.DuplicateHandle(hProcess, ctypes.c_void_p(hval), None, None, 0, False, 1)
                    offset += entry_size
        finally:
            k32.CloseHandle(hProcess)
    except Exception as e:
        log(f"Force close handles for pid {pid} error: {e}")


def reap_stale_server(port: int = 8780) -> None:
    """Убить любые зависшие процессы бэкенда, освободить порт 8780."""
    my_pid = os.getpid()

    # 1. Поиск PID на порту
    pids = get_pids_on_port(port)
    for pid in pids:
        if pid != my_pid:
            try:
                kill_process_tree_silent(int(pid))
                log(f"Reaped stale listener pid {pid} on port {port}")
            except Exception:
                pass

    # 2. Поиск любых python.exe / pythonw.exe с server.py в командной строке
    try:
        import psutil
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if p.pid == my_pid:
                    continue
                name = (p.info.get("name") or "").lower()
                if "python" in name:
                    cmdline = " ".join(p.info.get("cmdline") or []).lower()
                    if "server.py" in cmdline:
                        log(f"Reaped stale server.py process pid {p.pid}")
                        kill_process_tree_silent(p.pid)
            except Exception:
                pass
    except Exception:
        pass

    # 3. Гарантированно гасим accoreconsole.exe и фоновые acad.exe (/Automation)
    if os.name == "nt":
        for cmd in (
            ["taskkill", "/F", "/IM", "accoreconsole.exe"],
            ["taskkill", "/F", "/FI", "WINDOWTITLE eq ", "/IM", "acad.exe"],
        ):
            try:
                subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=5,
                    close_fds=True,
                    **hidden_process_kwargs(),
                )
            except Exception:
                pass

    # 4. Если порт все еще удерживается зомби-дескриптором, отзываем дескрипторы
    pids_remaining = get_pids_on_port(port)
    for r_pid in pids_remaining:
        if r_pid != my_pid:
            _force_close_process_handles(r_pid)


def find_or_start_server() -> tuple[int, subprocess.Popen | None]:
    target_port = 8780

    # 1. Проверяем, работает ли уже здоровый сервер на основном порту 8780
    if is_server_healthy(target_port):
        log("Found healthy server on primary port 8780, reusing instance")
        return target_port, None

    # 2. Если порт 8780 занят, но НЕ здоров — принудительно зачищаем старые процессы
    log("Port 8780 is occupied or unhealthy; reaping stale server process tree...")
    reap_stale_server(target_port)
    wait_deadline = time.time() + 3.0
    while time.time() < wait_deadline:
        if is_port_free(target_port):
            break
        time.sleep(0.3)
        reap_stale_server(target_port)

    log(f"Starting backend on port {target_port}")
    python_exe = _backend_python()
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    # Перенаправляем stdout и stderr в runtime/logs/server_startup.log для мгновенной фиксации ошибок старта
    startup_log_path = os.path.join(LOGS_DIR, "server_startup.log")
    os.makedirs(LOGS_DIR, exist_ok=True)
    try:
        startup_log = open(startup_log_path, "a", encoding="utf-8")
        startup_log.write(f"\n--- [{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting backend on port {target_port} ---\n")
        startup_log.flush()
    except Exception as e:
        log(f"Could not open server_startup.log: {e}")
        startup_log = subprocess.DEVNULL

    server_proc = subprocess.Popen(
        [python_exe, BACKEND, "--port", str(target_port)],
        cwd=REPO_ROOT,
        stdout=startup_log,
        stderr=startup_log,
        creationflags=creationflags,
        close_fds=True,
    )

    # Привязываем дочерний процесс сервера к Windows Job Object с авто-завершением
    assign_process_to_job(server_proc)

    deadline = time.time() + 20
    while time.time() < deadline:
        if server_proc.poll() is not None:
            log(f"Backend process pid {server_proc.pid} exited prematurely with return code {server_proc.returncode}!")
            break
        if is_server_healthy(target_port):
            log(f"Server on port {target_port} became healthy (pid {server_proc.pid})")
            return target_port, server_proc
        time.sleep(0.3)

    log(f"Warning: server on port {target_port} health check timed out, attempting to use it anyway")
    return target_port, server_proc


READINESS_TIMEOUT_SECONDS = 25


def fetch_json(url: str, timeout: float):
    """GET JSON; raise on non-200 status or unparseable body."""
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} for {url}")
        return json.loads(resp.read().decode("utf-8"))


def wait_for_objects_ready(base_url: str, timeout_seconds: float) -> tuple[bool, str]:
    """Poll GET /api/objects until HTTP 200 with parsed JSON.

    Bounded by timeout_seconds; polls the real condition (no fixed sleep
    used as synchronization, only a short poll interval inside the loop).
    """
    deadline = time.time() + max(0.1, timeout_seconds)
    last_error = "not attempted"
    while True:
        try:
            data = fetch_json(base_url + "api/objects", timeout=5)
            if isinstance(data, dict):
                return True, f"objects ready ({len(data.get('items', []))} items)"
            last_error = "unexpected payload (not a JSON object)"
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
        if time.time() >= deadline:
            return False, last_error
        time.sleep(0.3)


def startup_error_html(reason: str) -> str:
    safe = (reason or "unknown error")[:500]
    safe = safe.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
        "<title>F-Engineering Launcher — ошибка запуска</title></head>"
        "<body style='font-family:Segoe UI,sans-serif;background:#0f172a;color:#e2e8f0;padding:32px'>"
        "<h2>Launcher не смог запуститься</h2>"
        f"<p>Причина: {safe}</p>"
        "<p>Проверьте backend (http://127.0.0.1:8780/api/health) и перезапустите ярлык.</p>"
        "</body></html>"
    )


def show_startup_error(message: str) -> None:
    """One small error window instead of an empty blue maximized frame."""
    try:
        import webview
        webview.create_window(
            TITLE + " — ошибка запуска",
            html=startup_error_html(message),
            width=620,
            height=360,
        )
        webview.start()
    except Exception as e:
        log(f"startup error window failed: {e}")


def focus_existing_window() -> bool:
    try:
        user32 = ctypes.windll.user32
        for t in [TITLE, "F.E.R.O. Launcher v4", "F.E.R.O. Launcher", "FLauncher"]:
            hwnd = user32.FindWindowW(None, t)
            if hwnd:
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
                return True
    except Exception:
        pass
    return False


def open_browser_window(url: str) -> None:
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in edge_paths:
        if os.path.exists(p):
            profile = os.path.join(os.environ.get("LOCALAPPDATA", ""), "FEngineeringLauncher", "AppProfile")
            os.makedirs(profile, exist_ok=True)
            subprocess.Popen(
                [p, f"--app={url}", f"--user-data-dir={profile}", "--no-first-run", "--start-maximized"],
            )
            return

    import webbrowser
    webbrowser.open(url)


def main():
    readiness_deadline = time.time() + READINESS_TIMEOUT_SECONDS
    mutex = None
    try:
        mutex = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        mutex.bind(("127.0.0.1", GUI_MUTEX_PORT))
        if os.name == "nt":
            try:
                os.set_inheritable(mutex.fileno(), False)
                ctypes.windll.kernel32.SetHandleInformation(
                    int(mutex.fileno()), 1, 0  # HANDLE_FLAG_INHERIT = 1, 0 = disable inheritance
                )
            except Exception:
                pass
    except OSError:
        # Проверяем, действительно ли живо окно лаунчера
        try:
            if focus_existing_window():
                log("Focused existing window, exiting duplicate process")
                return
            else:
                log("Mutex busy and existing window could not be focused; checking for stale lock...")
                # Если окно не найдено — старый процесс завис или зомби.
                # Принудительно убиваем зависшие процессы, удерживающие GUI_MUTEX_PORT (8799)
                stale_pids = get_pids_on_port(GUI_MUTEX_PORT)
                for pid in stale_pids:
                    try:
                        log(f"Killing stale mutex holder pid {pid} on port {GUI_MUTEX_PORT}")
                        kill_process_tree_silent(int(pid))
                    except Exception:
                        pass
                # Ждем до 2.0 секунд освобождения сокета после завершения процесса
                wait_deadline = time.time() + 2.0
                rebound = False
                while time.time() < wait_deadline:
                    try:
                        mutex = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        mutex.bind(("127.0.0.1", GUI_MUTEX_PORT))
                        if os.name == "nt":
                            try:
                                os.set_inheritable(mutex.fileno(), False)
                                ctypes.windll.kernel32.SetHandleInformation(
                                    int(mutex.fileno()), 1, 0
                                )
                            except Exception:
                                pass
                        log("Successfully rebound GUI mutex port after reaping stale holder")
                        rebound = True
                        break
                    except OSError:
                        time.sleep(0.3)
                if not rebound:
                    log("Mutex port still busy after reaping attempt, exiting")
                    return
        except Exception as e:
            log(f"Mutex recovery failed: {e}")
            return

    port, server_proc = find_or_start_server()
    atexit.register(lambda: shutdown_server(server_proc, port))

    base_url = f"http://127.0.0.1:{port}/"

    # D1: objects readiness gate — no window exists yet.
    remaining = max(0.1, readiness_deadline - time.time())
    objects_ok, objects_detail = wait_for_objects_ready(base_url, remaining)
    if not objects_ok:
        log(f"Objects readiness failed: {objects_detail}")
        shutdown_server(server_proc, port)
        show_startup_error(f"objects endpoint failure: {objects_detail}")
        return
    log(f"Readiness: backend healthy, {objects_detail}")

    # D2: hidden window — never shown before all gates pass. No fullscreen.
    try:
        import webview
    except Exception as e:
        log(f"pywebview import failed: {e}, falling back to browser window")
        open_browser_window(base_url)
        return

    frontend_ready = threading.Event()
    window = webview.create_window(
        TITLE,
        base_url,
        hidden=True,
        width=1400,
        height=900,
        min_size=(1024, 700),
        text_select=True,
    )

    # D3: official pywebview frontend-ready signal.
    try:
        def _on_frontend_loaded(*args, **kwargs):
            frontend_ready.set()
        window.events.loaded += _on_frontend_loaded
    except Exception as e:
        log(f"Could not bind loaded event: {e}")

    # Гарантированное завершение сервера при закрытии окна
    try:
        def _on_window_closed(*args, **kwargs):
            log("Window closed event received, stopping server...")
            shutdown_server(server_proc, port)
        window.events.closed += _on_window_closed
    except Exception as e:
        log(f"Could not bind on_closed event: {e}")

    def _gatekeeper():
        # Exactly one show(): ready path maximizes after the gate,
        # timeout path shows the same window small with an error.
        try:
            remaining = max(0.1, readiness_deadline - time.time())
            if frontend_ready.wait(timeout=remaining):
                log("Readiness gates passed (health+objects+loaded); showing window once")
                window.show()
                try:
                    window.maximize()
                except Exception as e:
                    log(f"maximize failed: {e}")
            else:
                reason = "frontend load timeout"
                log(f"Readiness failed: {reason}")
                try:
                    window.resize(620, 360)
                except Exception:
                    pass
                try:
                    window.load_html(startup_error_html(reason))
                except Exception as e:
                    log(f"load_html failed: {e}")
                window.show()
        except Exception as e:
            log(f"gatekeeper failed: {e}")

    gatekeeper = threading.Thread(target=_gatekeeper, daemon=True)
    gatekeeper.start()
    try:
        webview.start(icon=ICON if os.path.exists(ICON) else None)
    except Exception as e:
        log(f"pywebview failed: {e}, falling back to browser window")
        open_browser_window(base_url)
        return
    # После выхода из webview.start() (окно закрыто)
    shutdown_server(server_proc, port)


if __name__ == "__main__":
    main()
