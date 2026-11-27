@echo off
chcp 65001 >nul
title FERA Analytic
start "" pythonw "%~dp0fera_analytic\app.pyw"
exit /b 0
