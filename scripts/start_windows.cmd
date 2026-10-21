@echo off
setlocal
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:: 1. Проверяем автономный переносимый Python
if exist "%~dp0..\runtime\python\pythonw.exe" (
    start "" "%~dp0..\runtime\python\pythonw.exe" "%~dp0..\app\flauncher.pyw"
    exit /b 0
)
if exist "%~dp0..\runtime\python\python.exe" (
    start "" "%~dp0..\runtime\python\python.exe" "%~dp0..\app\flauncher.pyw"
    exit /b 0
)

:: 2. Системный Python
if exist "C:\Python314\pythonw.exe" (
    start "" "C:\Python314\pythonw.exe" "%~dp0..\app\flauncher.pyw"
    exit /b 0
)
where pythonw >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    start "" pythonw "%~dp0..\app\flauncher.pyw"
    exit /b 0
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_app.ps1"
endlocal
