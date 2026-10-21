@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ========================================================
echo F-Engineering Launcher - CLI Agent Runner
echo Working Branch: dvg-main
echo Directory: %CD%
echo ========================================================

if "%~1"=="" (
    if not exist "prompt.txt" (
        echo [ERROR] prompt.txt not found in %CD%
        echo Please create prompt.txt with instructions for the agent,
        echo or pass prompt text directly as a command-line argument.
        exit /b 1
    )
    echo Executing agy with prompt.txt...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Get-Content prompt.txt -Raw; agy -p \"$p\" --dangerously-skip-permissions --mode accept-edits"
) else (
    echo Executing agy with argument...
    agy -p "%~1" --dangerously-skip-permissions --mode accept-edits
)
