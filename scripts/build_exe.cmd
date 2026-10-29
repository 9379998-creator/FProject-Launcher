@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0.."

where pyinstaller >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Установка PyInstaller...
    python -m pip install pyinstaller
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

python -m PyInstaller --noconfirm --clean "FProjectLauncher.spec"

if %ERRORLEVEL% EQU 0 (
    echo [OK] FEngineeringLauncher.exe собран в dist\FEngineeringLauncher\
    echo [INFO] Mirroring runtime structure ^(clean, without local caches or manifests^)...
    if exist "version.json" copy /Y "version.json" "dist\FEngineeringLauncher\" >nul
    if exist "app" xcopy /E /I /Q /Y "app" "dist\FEngineeringLauncher\app" >nul
    if exist "scripts" xcopy /E /I /Q /Y "scripts" "dist\FEngineeringLauncher\scripts" >nul
    mkdir "dist\FEngineeringLauncher\runtime\cache" 2>nul
    mkdir "dist\FEngineeringLauncher\runtime\logs" 2>nul
    mkdir "dist\FEngineeringLauncher\runtime\manifests" 2>nul
    mkdir "dist\FEngineeringLauncher\runtime\db" 2>nul
) else (
    echo [ERROR] Сборка завершилась с ошибкой.
    exit /b 1
)
