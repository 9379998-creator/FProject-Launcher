"""
build_protected_dist.py - Pipeline for compiling protected F.E.R.O. Launcher builds
Automates:
1. JavaScript minification and string obfuscation.
2. Embedding trial expiration and anti-tamper clock check.
3. Generating standalone C++ compiled binary via Nuitka.
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def obfuscate_javascript_simple(source_code: str) -> str:
    """
    Lightweight, robust Python-native JS minifier & comment stripper.
    Used when external node obfuscator is not installed.
    """
    # 1. Remove multi-line comments /* ... */
    clean = re.sub(r'/\*[\s\S]*?\*/', '', source_code)
    # 2. Remove single-line comments // ... (protecting http:// and https://)
    clean = re.sub(r'(?<![:"\'\\])//.*', '', clean)
    # 3. Collapse multiple empty lines
    lines = [line.rstrip() for line in clean.splitlines() if line.strip()]
    return "\n".join(lines)


def run_build(trial_days: int = 30, expiry_date: str = "", output_dir_name: str = "dist_protected") -> None:
    print("=" * 60)
    print(" F.E.R.O. LAUNCHER - PROTECTED BUILD PIPELINE")
    print("=" * 60)

    # 1. Determine expiration date
    if not expiry_date:
        target_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=trial_days)
        expiry_date = target_dt.strftime("%Y-%m-%d")

    print(f"[*] Срок действия ознакомительной версии: {expiry_date} ({trial_days} дней)")

    # 2. Prepare staging directory
    out_dir = REPO_ROOT / output_dir_name
    stage_dir = out_dir / "stage"
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Подготовка временного каталога сборки: {stage_dir}")

    # Copy app/ to stage
    shutil.copytree(REPO_ROOT / "app", stage_dir / "app")
    if (REPO_ROOT / "scripts").exists():
        shutil.copytree(REPO_ROOT / "scripts", stage_dir / "scripts")

    # 3. Configure license_guard.py in stage
    guard_path = stage_dir / "app" / "backend" / "license_guard.py"
    if guard_path.exists():
        content = guard_path.read_text(encoding="utf-8")
        content = re.sub(r'TRIAL_ENABLED:\s*bool\s*=\s*(False|True)', 'TRIAL_ENABLED: bool = True', content)
        content = re.sub(r'TRIAL_EXPIRY_DATE:\s*str\s*=\s*"[^"]*"', f'TRIAL_EXPIRY_DATE: str = "{expiry_date}"', content)
        guard_path.write_text(content, encoding="utf-8")
        print(f"[+] Защита лицензии встроена: TRIAL_ENABLED=True, EXPIRY={expiry_date}")

    # 4. Obfuscate frontend app.js
    frontend_app_js = stage_dir / "app" / "frontend" / "app.js"
    if frontend_app_js.exists():
        raw_js = frontend_app_js.read_text(encoding="utf-8")
        obfuscated = obfuscate_javascript_simple(raw_js)
        frontend_app_js.write_text(obfuscated, encoding="utf-8")
        print(f"[+] Фронтенд app.js очищен от комментариев и подготовлен к дистрибутиву ({len(raw_js)} -> {len(obfuscated)} байт)")

    # 5. Generate Nuitka compile script
    nuitka_cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--windows-disable-console",
        f"--windows-icon-from-ico={stage_dir / 'app' / 'frontend' / 'favicon.ico'}",
        f"--include-data-dir={stage_dir / 'app' / 'frontend'}=app/frontend",
        f"--output-dir={out_dir}",
        "--output-filename=FeroLauncher.exe",
        str(stage_dir / "app" / "flauncher.pyw")
    ]

    cmd_script_path = out_dir / "compile_nuitka.cmd"
    cmd_content = f"""@echo off
chcp 65001 >nul
echo ========================================================
echo  Компиляция F.E.R.O. Launcher в машинный C++ бинарник
echo ========================================================
python -m pip install --quiet nuitka ordered-set
{" ".join(f'"{arg}"' if " " in arg else arg for arg in nuitka_cmd)}
echo.
echo Сборка завершена: {out_dir}\\FeroLauncher.exe
pause
"""
    cmd_script_path.write_text(cmd_content, encoding="utf-8")
    print(f"[+] Сформирован скрипт компиляции Nuitka: {cmd_script_path}")
    print(f"[*] Для запуска компиляции выполните: {cmd_script_path}")
    print("=" * 60)
    print(" [OK] Конвейер безопасной сборки готов!")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build protected FERO Launcher distribution")
    parser.add_argument("--trial-days", type=int, default=30, help="Days until trial expires (default: 30)")
    parser.add_argument("--expires", type=str, default="", help="Expiration date in YYYY-MM-DD format")
    parser.add_argument("--out", type=str, default="dist_protected", help="Output directory")
    args = parser.parse_args()

    run_build(trial_days=args.trial_days, expiry_date=args.expires, output_dir_name=args.out)
