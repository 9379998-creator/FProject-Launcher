@echo off
setlocal
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0check_encoding.ps1"
endlocal
