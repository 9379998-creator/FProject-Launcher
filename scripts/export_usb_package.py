import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# Динамическое определение корня текущего репозитория лаунчера
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET_DIR = REPO_ROOT / "dist_release" / "FEngineering_Launcher_v4_Portable"
DEFAULT_ZIP_PATH = REPO_ROOT / "dist_release" / "FEngineering_Launcher_v4_Portable.zip"

EXCLUDE_DIRS = {
    "__pycache__", ".venv", "venv", "node_modules", "dist", "build", "dist_release",
    "renders", "output", "test", "idlelib", "ensurepip", "turtledemo", ".git"
}
EXCLUDE_EXTS = {".pyc", ".bak", ".tmp"}

def clean_copy_tree(src: Path, dst: Path, exclude_dirs=EXCLUDE_DIRS, exclude_exts=EXCLUDE_EXTS):
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for entry in src.iterdir():
        if entry.is_dir():
            if entry.name not in exclude_dirs:
                clean_copy_tree(entry, dst / entry.name, exclude_dirs, exclude_exts)
        else:
            if entry.suffix not in exclude_exts:
                shutil.copy2(entry, dst / entry.name)

def build_package(target_dir: Path = DEFAULT_TARGET_DIR, create_zip: bool = True):
    print("=" * 72)
    print("  F-Engineering Launcher v4 — Сборка автономного переносимого пакета")
    print("=" * 72)
    print(f"  Исходная папка: {REPO_ROOT}")
    print(f"  Целевая папка:  {target_dir}")
    print("=" * 72)

    # 1. Очистка и подготовка каталога назначения
    print("[1/7] Подготовка каталога назначения...", end=" ", flush=True)
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    target_dir.mkdir(parents=True, exist_ok=True)
    print("[OK]")

    # 2. Копирование кода приложения и скомпилированного EXE
    print("[2/7] Копирование компонентов приложения (app, scripts, tools, docs, EXE)...", end=" ", flush=True)
    for folder_name in ["app", "scripts", "docs"]:
        src_folder = REPO_ROOT / folder_name
        if src_folder.exists():
            clean_copy_tree(src_folder, target_dir / folder_name)

    # Копирование скомпилированного FEngineeringLauncher.exe и _internal (если собраны PyInstaller)
    dist_exe = REPO_ROOT / "dist" / "FEngineeringLauncher" / "FEngineeringLauncher.exe"
    dist_internal = REPO_ROOT / "dist" / "FEngineeringLauncher" / "_internal"
    if dist_exe.exists():
        shutil.copy2(dist_exe, target_dir / "FEngineeringLauncher.exe")
    if dist_internal.exists():
        clean_copy_tree(dist_internal, target_dir / "_internal")

    for root_file in ["README.md", "requirements.txt", "SETUP.cmd", "version.json"]:
        src_f = REPO_ROOT / root_file
        if src_f.exists():
            shutil.copy2(src_f, target_dir / root_file)
    print("[OK]")

    # 3. Создание структуры папок runtime
    print("[3/7] Создание структуры каталогов runtime...", end=" ", flush=True)
    runtime_dir = target_dir / "runtime"
    (runtime_dir / "cache").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "manifests").mkdir(parents=True, exist_ok=True)

    src_runtime = REPO_ROOT / "runtime"
    if (src_runtime / "tools").exists():
        clean_copy_tree(src_runtime / "tools", runtime_dir / "tools")
    if (src_runtime / "native_apps.json").exists():
        shutil.copy2(src_runtime / "native_apps.json", runtime_dir / "native_apps.json")
    if (src_runtime / "manifests").exists():
        clean_copy_tree(src_runtime / "manifests", runtime_dir / "manifests")
    print("[OK]")

    # 4. Формирование автономного Python (runtime/python)
    print("[4/7] Формирование автономного Python (runtime/python)...")
    python_src_dir = Path(r"C:\Python314")
    if not python_src_dir.exists():
        python_src_dir = Path(sys.executable).parent

    target_python = runtime_dir / "python"
    target_python.mkdir(parents=True, exist_ok=True)

    print("      Копирование ядра Python...", end=" ", flush=True)
    for f in python_src_dir.iterdir():
        if f.is_file() and (f.suffix.lower() in [".exe", ".dll"] or "python" in f.name.lower() and f.suffix.lower() == ".zip"):
            shutil.copy2(f, target_python / f.name)
    print("[OK]")

    print("      Копирование системных библиотек DLLs...", end=" ", flush=True)
    src_dlls = python_src_dir / "DLLs"
    if src_dlls.exists():
        clean_copy_tree(src_dlls, target_python / "DLLs")
    print("[OK]")

    print("      Копирование стандартной библиотеки Lib...", end=" ", flush=True)
    src_lib = python_src_dir / "Lib"
    if src_lib.exists():
        clean_copy_tree(src_lib, target_python / "Lib", exclude_dirs=EXCLUDE_DIRS | {"site-packages"})
    print("[OK]")

    print("      Копирование библиотек (PyMuPDF, openpyxl, pypdf, pywebview, psutil)...", end=" ", flush=True)
    target_sp = target_python / "Lib" / "site-packages"
    target_sp.mkdir(parents=True, exist_ok=True)

    sp_sources = [
        Path(os.environ.get("APPDATA", "")) / "Python" / "Python314" / "site-packages",
        python_src_dir / "Lib" / "site-packages"
    ]

    required_prefixes = [
        "fitz", "pymupdf", "openpyxl", "et_xmlfile", "pypdf",
        "webview", "pywebview", "bottle", "proxy_tools", "clr_loader",
        "pythonnet", "clr", "typing_extensions", "psutil", "win32",
        "win32api", "win32con", "win32gui", "win32process", "pywintypes",
        "pil", "pillow", "cryptography", "bcrypt"
    ]

    for sp_src in sp_sources:
        if sp_src.exists():
            for item in sp_src.iterdir():
                item_lower = item.name.lower()
                for pref in required_prefixes:
                    if item_lower.startswith(pref):
                        dest_item = target_sp / item.name
                        if not dest_item.exists():
                            if item.is_dir():
                                clean_copy_tree(item, dest_item)
                            else:
                                shutil.copy2(item, dest_item)
                        break
    print("[OK]")

    # 5. Упаковка портативного Poppler
    print("[5/7] Упаковка портативного Poppler (бинарники рендеринга PDF)...", end=" ", flush=True)
    poppler_sources = [
        Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages" / "oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe" / "poppler-25.07.0",
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "native" / "poppler"
    ]
    target_poppler = runtime_dir / "tools" / "poppler"
    poppler_found = False
    for ps in poppler_sources:
        if ps.exists():
            clean_copy_tree(ps, target_poppler)
            poppler_found = True
            break
    if poppler_found:
        print("[OK]")
    else:
        print("[ПРЕДУПРЕЖДЕНИЕ: Poppler не найден]")

    # 6. Создание запускалок и инструкций
    print("[6/7] Создание файлов быстрого запуска и инструкций...", end=" ", flush=True)

    # 6.1. Запуск_Лаунчера.cmd
    run_cmd_content = """@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

:: 0. Скомпилированный нативный EXE лаунчера
if exist "%~dp0FEngineeringLauncher.exe" (
    start "" "%~dp0FEngineeringLauncher.exe"
    exit /b 0
)

:: 1. Автономный портативный Python (внутри папки)
if exist "%~dp0runtime\\python\\pythonw.exe" (
    start "" "%~dp0runtime\\python\\pythonw.exe" "%~dp0app\\flauncher.pyw"
    exit /b 0
)
if exist "%~dp0runtime\\python\\python.exe" (
    start "" "%~dp0runtime\\python\\python.exe" "%~dp0app\\flauncher.pyw"
    exit /b 0
)

:: 2. Системный Python
if exist "C:\\Python314\\pythonw.exe" (
    start "" "C:\\Python314\\pythonw.exe" "%~dp0app\\flauncher.pyw"
    exit /b 0
)
where pythonw >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    start "" pythonw "%~dp0app\\flauncher.pyw"
    exit /b 0
)
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    start "" python "%~dp0app\\flauncher.pyw"
    exit /b 0
)

:: 3. Мастер проверки
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\\setup_pc.ps1"
endlocal
"""
    (target_dir / "Запуск_Лаунчера.cmd").write_text(run_cmd_content, encoding="utf-8")

    # 6.2. Создать_ярлык_на_Рабочем_столе.cmd
    create_shortcut_cmd = """@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "$wsh = New-Object -ComObject WScript.Shell; " ^
    "$desktop = [Environment]::GetFolderPath('Desktop'); " ^
    "$shortcut = $wsh.CreateShortcut(\\"$desktop\\F-Engineering Launcher.lnk\\"); " ^
    "$exe = Join-Path '%~dp0' 'FEngineeringLauncher.exe'; " ^
    "$pyw = Join-Path '%~dp0' 'runtime\\python\\pythonw.exe'; " ^
    "$app = Join-Path '%~dp0' 'app\\flauncher.pyw'; " ^
    "$runCmd = Join-Path '%~dp0' 'Запуск_Лаунчера.cmd'; " ^
    "$ico = Join-Path '%~dp0' 'app\\frontend\\assets\\flauncher.ico'; " ^
    "if (Test-Path $exe) { $shortcut.TargetPath = $exe; $shortcut.WorkingDirectory = '%~dp0'; } " ^
    "elseif (Test-Path $pyw) { $shortcut.TargetPath = $pyw; $shortcut.Arguments = '\\"' + $app + '\\"'; $shortcut.WorkingDirectory = '%~dp0'; } " ^
    "else { $shortcut.TargetPath = $runCmd; $shortcut.WorkingDirectory = '%~dp0'; }; " ^
    "$shortcut.Description = 'F-Engineering Launcher v4'; " ^
    "if (Test-Path $ico) { $shortcut.IconLocation = $ico + ',0'; }; " ^
    "$shortcut.Save(); " ^
    "Write-Host ''; Write-Host '  [OK] Ярлык F-Engineering Launcher успешно создан на вашем Рабочем столе!' -ForegroundColor Green; Write-Host ''"
pause
endlocal
"""
    (target_dir / "Создать_ярлык_на_Рабочем_столе.cmd").write_text(create_shortcut_cmd, encoding="utf-8")

    # 6.2b. Тест_компьютера.cmd
    pc_test_cmd = """@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\\setup_pc.ps1"
pause
endlocal
"""
    (target_dir / "Тест_компьютера.cmd").write_text(pc_test_cmd, encoding="utf-8")

    # 6.3. ИНСТРУКЦИЯ_БЫСТРЫЙ_СТАРТ.txt
    instruction_text = """========================================================================
   F-Engineering Launcher v4 — Автономная переносимая версия
========================================================================

Данная папка содержит ПОЛНОСТЬЮ АВТОНОМНЫЙ лаунчер инженерной документации.
Для работы НЕ ТРЕБУЕТСЯ устанавливать Python, библиотеки или настройки.
Все необходимые компоненты и библиотеки уже включены в комплект!

------------------------------------------------------------------------
КАК ПОЛЬЗОВАТЬСЯ НА ЛЮБОМ КОМПЬЮТЕРЕ:
------------------------------------------------------------------------

ВАРИАНТ 1 (Рекомендуемый — запуск через нативный EXE или ярлык):
1. Скопируйте папку «FEngineering_Launcher_v4_Portable» на диск C:\\ или D:\\
   (например, в «C:\\FEngineering_Launcher»).
2. Зайдите в папку и дважды кликните «Создать_ярлык_на_Рабочем_столе.cmd».
3. Запускайте лаунчер в любой момент прямо с Рабочего стола!
   (Либо запускайте напрямую файл «FEngineeringLauncher.exe»).

ВАРИАНТ 2 (Прямо с флешки без копирования):
1. Вставьте флешку в любой компьютер с Windows.
2. Дважды кликните по «FEngineeringLauncher.exe» (или «Запуск_Лаунчера.cmd»).
3. Лаунчер сразу откроется в отдельном окне приложения.

------------------------------------------------------------------------
ШТАТНЫЕ ПРОГРАММЫ (AutoCAD, Word, Excel):
------------------------------------------------------------------------
- Лаунчер открывает файлы через программы, установленные на данном компьютере.
- Если на компьютере установлен AutoCAD — чертежи DWG откроются в нём.
- Если на компьютере установлен MS Office — таблицы и документы откроются в них.
- Если офиса или САПР нет — таблицы XLSX и чертежи (с PDF-парами) всё равно
  будут полноценно открываться и просматриваться во встроенном окне лаунчера!

Приятной работы!
"""
    (target_dir / "ИНСТРУКЦИЯ_БЫСТРЫЙ_СТАРТ.txt").write_text(instruction_text, encoding="utf-8")
    print("[OK]")

    # 7. Тестовая верификация
    print("[7/7] Проверка работоспособности автономной сборки...", end=" ", flush=True)
    test_py = target_python / "python.exe"
    if test_py.exists():
        proc = subprocess.run(
            [str(test_py), "-c", "import fitz, openpyxl, pypdf, webview; print('VERIFY_SUCCESS')"],
            capture_output=True, text=True
        )
        if "VERIFY_SUCCESS" in proc.stdout:
            print("[OK]")
            print("      Автономный Python успешно загружает fitz, openpyxl, pypdf, webview.")
        else:
            print(f"[ПРЕДУПРЕЖДЕНИЕ: {proc.stderr.strip()}]")
    else:
        print("[ОШИБКА: python.exe не найден]")

    # Подсчет размера
    total_bytes = sum(f.stat().st_size for f in target_dir.rglob("*") if f.is_file())
    total_mb = round(total_bytes / (1024 * 1024), 1)

    print()
    print("=" * 72)
    print("  СБОРКА УСПЕШНО ЗАВЕРШЕНА!")
    print(f"  Размер переносимой папки: {total_mb} МБ")
    print(f"  Каталог: {target_dir}")
    print("=" * 72)

    # Создание единого ZIP архива
    if create_zip:
        print()
        print("Создание единого ZIP-архива для отправки коллегам...", end=" ", flush=True)
        DEFAULT_ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
        if DEFAULT_ZIP_PATH.exists():
            DEFAULT_ZIP_PATH.unlink()

        with zipfile.ZipFile(DEFAULT_ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in target_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(target_dir)
                    zf.write(file_path, arcname)
        zip_mb = round(DEFAULT_ZIP_PATH.stat().st_size / (1024 * 1024), 1)
        print(f"[OK] ({zip_mb} МБ)")
        print(f"  Архив готов: {DEFAULT_ZIP_PATH}")

    print()
    print("Готово к переносу на флешку или передаче коллегам!")
    print()

if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET_DIR
    build_package(target)
