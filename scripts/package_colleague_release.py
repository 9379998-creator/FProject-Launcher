import os
import shutil
import zipfile
from pathlib import Path

REPO_ROOT = Path(r"C:\Users\a9379\.gemini\antigravity\scratch\FProject-Launcher")
INSTALLED_APP = Path(r"C:\Users\a9379\AppData\Local\FEngineering_Launcher")
BUILD_DIR = Path(r"C:\Users\a9379\.gemini\antigravity\scratch\dist_colleague")
TARGET_FOLDER = BUILD_DIR / "FEngineering_Launcher_v4"
ZIP_OUTPUT = BUILD_DIR / "FEngineering_Launcher_v4_Portable.zip"

print(f"[*] Сборка портативного релиза F-Engineering Launcher v4.4.0...")
print(f"[*] Репозиторий: {REPO_ROOT}")
print(f"[*] Среда выполнения: {INSTALLED_APP}")

if TARGET_FOLDER.exists():
    shutil.rmtree(TARGET_FOLDER, ignore_errors=True)
TARGET_FOLDER.mkdir(parents=True, exist_ok=True)

# 1. Бинарник EXE и скомпилированный рантайм _internal
print("[1] Копирование исполняемых компонентов...")
shutil.copy2(INSTALLED_APP / "FEngineeringLauncher.exe", TARGET_FOLDER / "FEngineeringLauncher.exe")
shutil.copytree(INSTALLED_APP / "_internal", TARGET_FOLDER / "_internal", dirs_exist_ok=True)

# 2. Исходники app и scripts прямо из актуального Git репозитория
print("[2] Копирование актуальных модулей app и scripts из Git-репозитория...")
shutil.copytree(
    REPO_ROOT / "app",
    TARGET_FOLDER / "app",
    dirs_exist_ok=True,
    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.tmp")
)
# Синхронизируем также внутрь _internal/app для гарантированного импорта
shutil.copytree(
    REPO_ROOT / "app",
    TARGET_FOLDER / "_internal" / "app",
    dirs_exist_ok=True,
    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.tmp")
)
shutil.copytree(
    REPO_ROOT / "scripts",
    TARGET_FOLDER / "scripts",
    dirs_exist_ok=True,
    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.tmp")
)

# 3. Чистые runtime каталоги и Poppler
print("[3] Подготовка чистых каталогов runtime...")
for sub in ["cache", "logs", "manifests", "db"]:
    (TARGET_FOLDER / "runtime" / sub).mkdir(parents=True, exist_ok=True)

if (INSTALLED_APP / "runtime" / "tools").exists():
    print("[3.1] Интеграция автономного Poppler (runtime/tools)...")
    shutil.copytree(INSTALLED_APP / "runtime" / "tools", TARGET_FOLDER / "runtime" / "tools", dirs_exist_ok=True)

# 4. Метаданные и правила
print("[4] Копирование version.json и регламентов...")
shutil.copy2(REPO_ROOT / "version.json", TARGET_FOLDER / "version.json")
if (REPO_ROOT / "AGENTS.md").exists():
    shutil.copy2(REPO_ROOT / "AGENTS.md", TARGET_FOLDER / "AGENTS.md")

# 5. Скрипты запуска в 1 клик
print("[5] Генерация bat/cmd сценариев запуска...")
bat_content = """@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo ========================================================================
echo    F-Engineering Launcher v4.4 — Инженерное бюро ООО «ФЕРО»
echo ========================================================================
echo.

if exist "%~dp0FEngineeringLauncher.exe" (
    echo [OK] Запуск FEngineeringLauncher.exe...
    start "" "%~dp0FEngineeringLauncher.exe"
    exit /b 0
)

if exist "%~dp0runtime\\python\\pythonw.exe" (
    echo [OK] Запуск через автономный Python...
    start "" "%~dp0runtime\\python\\pythonw.exe" "%~dp0app\\flauncher.pyw"
    exit /b 0
)

where pythonw >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] Запуск через системный pythonw...
    start "" pythonw "%~dp0app\\flauncher.pyw"
    exit /b 0
)

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] Запуск через системный python...
    start "" python "%~dp0app\\flauncher.pyw"
    exit /b 0
)

echo [ОШИБКА] Не удалось найти FEngineeringLauncher.exe или Python!
echo Пожалуйста, убедитесь, что архив распакован полностью.
pause
exit /b 1
"""
(TARGET_FOLDER / "Запуск_Лаунчера.bat").write_text(bat_content, encoding="utf-8")
(TARGET_FOLDER / "Запуск_Лаунчера.cmd").write_text(bat_content, encoding="utf-8")

shortcut_content = """@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo Создание ярлыка F-Engineering Launcher на Рабочем столе...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$desktop = [Environment]::GetFolderPath('Desktop'); " ^
    "$shortcutPath = [System.IO.Path]::Combine($desktop, 'F-Engineering Launcher.lnk'); " ^
    "$s = $ws.CreateShortcut($shortcutPath); " ^
    "if (Test-Path '%~dp0FEngineeringLauncher.exe') { " ^
    "    $s.TargetPath = '%~dp0FEngineeringLauncher.exe'; " ^
    "} else { " ^
    "    $s.TargetPath = '%~dp0Запуск_Лаунчера.bat'; " ^
    "} " ^
    "$s.WorkingDirectory = '%~dp0'; " ^
    "$s.Description = 'F-Engineering Launcher v4.4 — Инженерное бюро ООО ФЕРО'; " ^
    "if (Test-Path '%~dp0app\\frontend\\assets\\flauncher.ico') { " ^
    "    $s.IconLocation = '%~dp0app\\frontend\\assets\\flauncher.ico,0'; " ^
    "} " ^
    "$s.Save(); " ^
    "Write-Host '[OK] Ярлык успешно создан на Рабочем столе!' -ForegroundColor Green"

pause
endlocal
"""
(TARGET_FOLDER / "Создать_ярлык_на_Рабочем_столе.bat").write_text(shortcut_content, encoding="utf-8")
(TARGET_FOLDER / "Создать_ярлык_на_Рабочем_столе.cmd").write_text(shortcut_content, encoding="utf-8")

# 6. Инструкция для коллеги
instruction_content = """========================================================================
   F-Engineering Launcher v4.4 — ООО «ФЕРО» (Инженерное бюро)
   Инженерный вьювер и диспетчер рабочей проектной документации
   Релиз от 10 ноября 2026 г. (Стабильная поддержка DWG)
========================================================================

ИНСТРУКЦИЯ ПО ЗАПУСКУ ДЛЯ СОТРУДНИКОВ:

1. БЫСТРЫЙ ЗАПУСК:
   • Распакуйте архив в любую удобную папку на вашем компьютере (например: C:\\FEngineering_Launcher).
   • Запустите файл «Запуск_Лаунчера.bat» (или дважды кликните на «FEngineeringLauncher.exe»).
   • Программа запустится сразу. Установка Python, системных драйверов и прав администратора НЕ ТРЕБУЕТСЯ (все библиотеки, движки и автономный Poppler уже встроены).

2. СОЗДАНИЕ ЯРЛЫКА НА РАБОЧЕМ СТОЛЕ:
   • Запустите файл «Создать_ярлык_на_Рабочем_столе.bat».
   • На вашем Рабочем столе появится фирменный значок FERO для запуска в 1 клик.

3. КЛЮЧЕВЫЕ ВОЗМОЖНОСТИ РЕЛИЗА 4.4:
   • Полноценный и устойчивый просмотр чертежей DWG (любой сложности и объема):
     - Мгновенный отклик и плавное листание многостраничных альбомов без запуска тяжелого AutoCAD.
     - Защита от зависаний и сбоев: оптимизированный экспорт без раздувания шрифтовых аннотаций SHX.
     - Плавающая панель прогресса: окно статуса теперь можно свободно перемещать мышью по экрану за шапку и сворачивать кнопкой «−», чтобы оно не закрывало чертеж.
   • Мгновенная каталогизация и навигация по проектным папкам объектов (PDF, DWG, DXF, XLSX, DOCX).
   • Высокоскоростной просмотр векторных PDF (DPI 72/150/300) с панорамированием, масштабированием и разворотом.
   • Автономный просмотр таблиц Excel и документов Word без открытия Microsoft Office.
   • Формирование Инженерного паспорта объекта с декомпозицией разделов АР/КМ.

4. ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ:
   • ОС: Windows 10 / 11 (64-bit).
   • Права администратора: не требуются.
========================================================================
"""
(TARGET_FOLDER / "ИНСТРУКЦИЯ_ДЛЯ_КОЛЛЕГИ.txt").write_text(instruction_content, encoding="utf-8")

# 7. Архивация в ZIP
print("[6] Упаковка в автономный ZIP архив...")
if ZIP_OUTPUT.exists():
    ZIP_OUTPUT.unlink()

file_count = 0
with zipfile.ZipFile(ZIP_OUTPUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for root, _, files in os.walk(TARGET_FOLDER):
        for f in files:
            fp = Path(root) / f
            arcname = fp.relative_to(BUILD_DIR)
            zf.write(fp, arcname)
            file_count += 1

zip_mb = round(ZIP_OUTPUT.stat().st_size / (1024 * 1024), 1)
print(f"[OK] Сборка завершена! Упаковано файлов: {file_count}, размер ZIP: {zip_mb} МБ ({ZIP_OUTPUT.stat().st_size:,} байт)")

# 8. Деплой в папку Documents и на Google Диск
print("\n[7] Деплой релизных пакетов...")

# А. Локальная папка для быстрой пересылки
DOCS_RELEASE = Path(r"C:\Users\a9379\Documents\FERO_Launcher_v4_Release")
DOCS_RELEASE.mkdir(parents=True, exist_ok=True)
shutil.copy2(ZIP_OUTPUT, DOCS_RELEASE / "FEngineering_Launcher_v4_Portable.zip")
shutil.copy2(TARGET_FOLDER / "Запуск_Лаунчера.bat", DOCS_RELEASE / "Запуск_Лаунчера.bat")
shutil.copy2(TARGET_FOLDER / "Создать_ярлык_на_Рабочем_столе.bat", DOCS_RELEASE / "Создать_ярлык_на_Рабочем_столе.bat")
shutil.copy2(TARGET_FOLDER / "ИНСТРУКЦИЯ_ДЛЯ_КОЛЛЕГИ.txt", DOCS_RELEASE / "ИНСТРУКЦИЯ_ДЛЯ_КОЛЛЕГИ.txt")
print(f"[OK] Скопировано в локальную папку: {DOCS_RELEASE}")

# Б. Корпоративный Google Диск
GDRIVE_DIR = Path(r"G:\Общие диски\022_F-Engineering\01_Launcher")
if GDRIVE_DIR.exists():
    shutil.copy2(ZIP_OUTPUT, GDRIVE_DIR / "FEngineering_Launcher_v4_Portable.zip")
    shutil.copy2(TARGET_FOLDER / "Запуск_Лаунчера.bat", GDRIVE_DIR / "Запуск_Лаунчера.bat")
    shutil.copy2(TARGET_FOLDER / "Создать_ярлык_на_Рабочем_столе.bat", GDRIVE_DIR / "Создать_ярлык_на_Рабочем_столе.bat")
    shutil.copy2(TARGET_FOLDER / "ИНСТРУКЦИЯ_ДЛЯ_КОЛЛЕГИ.txt", GDRIVE_DIR / "ИНСТРУКЦИЯ_ДЛЯ_КОЛЛЕГИ.txt")
    print(f"[OK] Скопировано на Google Диск: {GDRIVE_DIR}")
else:
    print(f"[!] Предупреждение: Google Диск {GDRIVE_DIR} не доступен.")

# 9. Проверка целостности
print("\n[8] Проверка целостности созданного ZIP архива...")
with zipfile.ZipFile(ZIP_OUTPUT, 'r') as zf:
    bad_file = zf.testzip()
    if bad_file:
        raise RuntimeError(f"Поврежден файл в архиве: {bad_file}")
    print(f"[OK] Все {len(zf.infolist())} контрольных сумм CRC32 в архиве валидны!")

print("\n=== ВСЕ ЭТАПЫ СБОРКИ И ДЕПЛОЯ УСПЕШНО ЗАВЕРШЕНЫ ===")
