# -*- coding: utf-8 -*-
"""
FERA Analytic GUI — Автономный модуль аудита и формирования Паспорта объекта
Стиль: Apple Minimalist (3 пастельных тона: #FFFFFF, #F5F5F7, #1D1D1F)
"""

import os
import sys
import json
import threading
import subprocess
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Добавляем родительский путь для импорта engine
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

try:
    import engine
except ImportError:
    from fera_analytic import engine


CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FERA_Analytic"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_last_path() -> str:
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("last_project_dir", "")
    except Exception:
        pass
    return ""


def save_last_path(path_str: str) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_project_dir": path_str}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class FeraAnalyticApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("FERA Analytic — Паспорт объекта и Расчет объемов")
        self.geometry("820x600")
        self.minsize(740, 520)
        self.configure(bg="#FFFFFF")

        # Результаты работы
        self.artifacts = {}
        self.is_running = False

        self._setup_styles()
        self._build_ui()

        # Восстановление последнего пути
        last_dir = load_last_path()
        if last_dir and os.path.exists(last_dir):
            self.entry_path.insert(0, last_dir)

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        # Прогресс-бар Apple Style
        style.configure(
            "Apple.Horizontal.TProgressbar",
            background="#1D1D1F",
            troughcolor="#E5E5EA",
            bordercolor="#E5E5EA",
            lightcolor="#1D1D1F",
            darkcolor="#1D1D1F"
        )

    def _build_ui(self):
        # 1. Заглавный блок (Apple Minimalist)
        header_frame = tk.Frame(self, bg="#FFFFFF", padx=28, pady=18)
        header_frame.pack(fill=tk.X)

        lbl_brand = tk.Label(
            header_frame,
            text="ИНЖЕНЕРНОЕ БЮРО FERO",
            font=("Segoe UI", 9, "bold"),
            fg="#86868B",
            bg="#FFFFFF"
        )
        lbl_brand.pack(anchor="w")

        lbl_title = tk.Label(
            header_frame,
            text="FERA Analytic",
            font=("Segoe UI", 20, "bold"),
            fg="#1D1D1F",
            bg="#FFFFFF"
        )
        lbl_title.pack(anchor="w", pady=(2, 0))

        lbl_desc = tk.Label(
            header_frame,
            text="Автономный модуль аудита документации, детекции коллизий и генерации Паспорта объекта",
            font=("Segoe UI", 10),
            fg="#86868B",
            bg="#FFFFFF"
        )
        lbl_desc.pack(anchor="w", pady=(2, 0))

        # Разделитель
        sep = tk.Frame(self, height=1, bg="#E5E5EA")
        sep.pack(fill=tk.X, padx=28)

        # 2. Выбор папки объекта
        input_frame = tk.Frame(self, bg="#FFFFFF", padx=28, pady=16)
        input_frame.pack(fill=tk.X)

        lbl_folder = tk.Label(
            input_frame,
            text="Рабочая папка объекта с чертежами (DWG / PDF / XLS):",
            font=("Segoe UI", 10, "bold"),
            fg="#1D1D1F",
            bg="#FFFFFF"
        )
        lbl_folder.pack(anchor="w", pady=(0, 6))

        row_picker = tk.Frame(input_frame, bg="#FFFFFF")
        row_picker.pack(fill=tk.X)

        self.entry_path = tk.Entry(
            row_picker,
            font=("Segoe UI", 10),
            bg="#F5F5F7",
            fg="#1D1D1F",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#E5E5EA",
            highlightcolor="#1D1D1F"
        )
        self.entry_path.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 10))

        btn_browse = tk.Button(
            row_picker,
            text="Обзор…",
            font=("Segoe UI", 10),
            bg="#F5F5F7",
            fg="#1D1D1F",
            relief=tk.FLAT,
            padx=16,
            pady=4,
            cursor="hand2",
            command=self._on_browse
        )
        btn_browse.pack(side=tk.RIGHT)

        # 3. Кнопка запуска
        action_frame = tk.Frame(self, bg="#FFFFFF", padx=28, pady=4)
        action_frame.pack(fill=tk.X)

        self.btn_run = tk.Button(
            action_frame,
            text="▶  Сформировать Паспорт и Расчет объемов",
            font=("Segoe UI", 11, "bold"),
            bg="#1D1D1F",
            fg="#FFFFFF",
            activebackground="#333336",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            pady=9,
            cursor="hand2",
            command=self._on_run_audit
        )
        self.btn_run.pack(fill=tk.X)

        # 4. Прогресс и статус
        self.progress_frame = tk.Frame(self, bg="#FFFFFF", padx=28, pady=10)
        self.progress_frame.pack(fill=tk.X)

        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            style="Apple.Horizontal.TProgressbar",
            mode="determinate"
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 6))

        self.lbl_status = tk.Label(
            self.progress_frame,
            text="Готов к работе. Выберите папку объекта и нажмите кнопку запуска.",
            font=("Segoe UI", 9.5),
            fg="#86868B",
            bg="#FFFFFF"
        )
        self.lbl_status.pack(anchor="w")

        # 5. Текстовый журнал выполнения
        log_frame = tk.Frame(self, bg="#FFFFFF", padx=28, pady=4)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.txt_log = tk.Text(
            log_frame,
            bg="#F5F5F7",
            fg="#1D1D1F",
            font=("Consolas", 9.5),
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#E5E5EA",
            padx=12,
            pady=10
        )
        self.txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.txt_log.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_log.configure(yscrollcommand=scroll.set)

        # 6. Панель открытия результатов (активируется по завершении)
        self.result_frame = tk.Frame(self, bg="#FFFFFF", padx=28, pady=16)
        self.result_frame.pack(fill=tk.X)

        self.btn_open_html = tk.Button(
            self.result_frame,
            text="📄  Открыть Паспорт (HTML)",
            font=("Segoe UI", 10, "bold"),
            bg="#F5F5F7",
            fg="#1D1D1F",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            state=tk.DISABLED,
            cursor="hand2",
            command=self._on_open_html
        )
        self.btn_open_html.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_open_excel = tk.Button(
            self.result_frame,
            text="📊  Открыть Расчет (Excel)",
            font=("Segoe UI", 10, "bold"),
            bg="#F5F5F7",
            fg="#1D1D1F",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            state=tk.DISABLED,
            cursor="hand2",
            command=self._on_open_excel
        )
        self.btn_open_excel.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_open_folder = tk.Button(
            self.result_frame,
            text="📁  Папка с отчетами",
            font=("Segoe UI", 10),
            bg="#F5F5F7",
            fg="#86868B",
            relief=tk.FLAT,
            padx=12,
            pady=6,
            state=tk.DISABLED,
            cursor="hand2",
            command=self._on_open_folder
        )
        self.btn_open_folder.pack(side=tk.RIGHT)

    def _log(self, text: str):
        self.txt_log.insert(tk.END, text + "\n")
        self.txt_log.see(tk.END)

    def _on_browse(self):
        folder = filedialog.askdirectory(title="Выберите папку объекта с чертежами")
        if folder:
            self.entry_path.delete(0, tk.END)
            self.entry_path.insert(0, folder)
            save_last_path(folder)

    def _update_progress_ui(self, percent: int, msg: str):
        self.progress_bar["value"] = percent
        self.lbl_status.config(text=msg)
        self._log(f"[{percent:3d}%] {msg}")

    def _on_run_audit(self):
        if self.is_running:
            return

        proj_dir = self.entry_path.get().strip()
        if not proj_dir or not os.path.isdir(proj_dir):
            messagebox.showwarning("Внимание", "Укажите корректную папку проекта с чертежами.")
            return

        save_last_path(proj_dir)

        self.is_running = True
        self.btn_run.config(state=tk.DISABLED, text="⏳ Выполняется расчет и аудит…")
        self.btn_open_html.config(state=tk.DISABLED)
        self.btn_open_excel.config(state=tk.DISABLED)
        self.btn_open_folder.config(state=tk.DISABLED)
        self.txt_log.delete("1.0", tk.END)
        self.progress_bar["value"] = 0

        self._log(f"--- НАЧАЛО АУДИТА: {os.path.basename(proj_dir)} ---")
        self._log(f"Каталог: {proj_dir}")

        def worker():
            try:
                def cb(pct, message):
                    self.after(0, self._update_progress_ui, pct, message)

                res = engine.run_audit(proj_dir, progress_cb=cb)
                self.artifacts = res

                def on_done():
                    self.is_running = False
                    self.btn_run.config(state=tk.NORMAL, text="▶  Сформировать Паспорт и Расчет объемов")
                    self.btn_open_html.config(state=tk.NORMAL)
                    self.btn_open_excel.config(state=tk.NORMAL)
                    self.btn_open_folder.config(state=tk.NORMAL)
                    self._log("--- АУДИТ УСПЕШНО ЗАВЕРШЕН ---")
                    self._log(f"Паспорт HTML: {res['passport_html']}")
                    self._log(f"Расчет Excel: {res['excel_vor']}")
                    messagebox.showinfo("Успешно", "Паспорт объекта и расчет объемов сформированы!")

                self.after(0, on_done)
            except Exception as e:
                def on_err(err_msg):
                    self.is_running = False
                    self.btn_run.config(state=tk.NORMAL, text="▶  Сформировать Паспорт и Расчет объемов")
                    self._log(f"ОШИБКА: {err_msg}")
                    messagebox.showerror("Ошибка аудита", f"Произошла ошибка при выполнении аудита:\n{err_msg}")

                self.after(0, on_err, str(e))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _on_open_html(self):
        p = self.artifacts.get("passport_html")
        if p and os.path.exists(p):
            os.startfile(p)

    def _on_open_excel(self):
        p = self.artifacts.get("excel_vor")
        if p and os.path.exists(p):
            os.startfile(p)

    def _on_open_folder(self):
        p = self.artifacts.get("output_dir")
        if p and os.path.exists(p):
            os.startfile(p)


if __name__ == "__main__":
    app = FeraAnalyticApp()
    app.mainloop()
