param(
    [string]$TargetDrive = ""
)

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "   F-Engineering Launcher v3 — Запись на флешку (USB Auto-Deploy)      " -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

$sourcePortable = "C:\Codex\FEngineering_Launcher_Portable"
$sourceZip = "C:\Codex\FEngineering_Launcher_v3_Portable.zip"

if (-not (Test-Path $sourcePortable) -or -not (Test-Path $sourceZip)) {
    Write-Host "Локальная сборка не найдена в C:\Codex. Запуск сборщика..." -ForegroundColor Yellow
    python "C:\Users\a9379\Documents\Codex\FEngineering_Launcher_v3\scripts\export_usb_package.py"
}

# 1. Поиск флешки
$drive = $null
if ($TargetDrive -ne "") {
    $cleanDrive = $TargetDrive.TrimEnd('\')
    $drive = Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DeviceId -eq $cleanDrive }
}

if (-not $drive) {
    $removables = @(Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -eq 2 })
    if ($removables.Count -eq 1) {
        $drive = $removables[0]
    } elseif ($removables.Count -gt 1) {
        Write-Host "Найдено несколько флешек:" -ForegroundColor Yellow
        for ($i = 0; $i -lt $removables.Count; $i++) {
            $freeGb = [math]::Round($removables[$i].FreeSpace / 1GB, 1)
            $sizeGb = [math]::Round($removables[$i].Size / 1GB, 1)
            Write-Host "  [$($i+1)] $($removables[$i].DeviceId) ($($removables[$i].VolumeName)) — Свободно: $freeGb ГБ из $sizeGb ГБ"
        }
        $choice = Read-Host "Выберите номер диска (1-$($removables.Count))"
        $drive = $removables[[int]$choice - 1]
    }
}

if (-not $drive) {
    Write-Host "Флешка пока не обнаружена." -ForegroundColor Yellow
    Write-Host "--> Вставьте флешку в USB-порт компьютера..." -ForegroundColor Green
    Write-Host "Ожидание подключения..." -NoNewline
    
    while (-not $drive) {
        Start-Sleep -Seconds 2
        Write-Host "." -NoNewline
        $found = @(Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -eq 2 })
        if ($found.Count -gt 0) {
            $drive = $found[0]
            Write-Host ""
            break
        }
    }
}

$usbRoot = "$($drive.DeviceId)\"
$freeMb = [math]::Round($drive.FreeSpace / 1MB, 0)
Write-Host ""
Write-Host "Обнаружена флешка: $($drive.DeviceId) [$($drive.VolumeName)]" -ForegroundColor Green
Write-Host "Свободно на флешке: $freeMb МБ"
Write-Host ""

if ($freeMb -lt 300) {
    Write-Host "ОШИБКА: На флешке меньше 300 МБ свободного места!" -ForegroundColor Red
    exit 1
}

# 2. Запись файлов
Write-Host "[1/4] Копирование автономной папки FEngineering_Launcher на флешку..." -ForegroundColor Cyan
$destFolder = Join-Path $usbRoot "FEngineering_Launcher"
if (-not (Test-Path $destFolder)) {
    New-Item -ItemType Directory -Force -Path $destFolder | Out-Null
}

$robocopy = robocopy $sourcePortable $destFolder /E /R:1 /W:1 /NFL /NDL /NP /NJH /NJS
Write-Host "      Папка FEngineering_Launcher скопирована." -ForegroundColor Green

Write-Host "[2/4] Копирование архива FEngineering_Launcher_v3_Portable.zip..." -ForegroundColor Cyan
Copy-Item $sourceZip -Destination (Join-Path $usbRoot "FEngineering_Launcher_v3_Portable.zip") -Force
Write-Host "      ZIP-архив скопирован." -ForegroundColor Green

Write-Host "[3/4] Создание корневых файлов быстрого запуска на флешке..." -ForegroundColor Cyan

# Файл прямого запуска
$runCmd = @'
@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0FEngineering_Launcher"
call "Запуск_Лаунчера.cmd"
endlocal
'@
[System.IO.File]::WriteAllText((Join-Path $usbRoot "🚀_Запуск_Лаунчера.cmd"), $runCmd, [System.Text.Encoding]::UTF8)

# Файл установки на компьютер
$installCmd = @'
@echo off
setlocal
chcp 65001 >nul
echo ========================================================================
echo    Установка F-Engineering Launcher на данный компьютер
echo ========================================================================
echo.
echo Копирование файлов программы в локальный профиль пользователя...
set "TARGET_DIR=%LOCALAPPDATA%FEngineering_Launcher"
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"
xcopy "%~dp0FEngineering_Launcher*" "%TARGET_DIR%" /E /I /Y /Q >nul

echo Создание ярлыка на Рабочем столе...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$wsh = New-Object -ComObject WScript.Shell; $desktop = [Environment]::GetFolderPath('Desktop'); $s = $wsh.CreateShortcut("$desktopF-Engineering Launcher.lnk"); $s.TargetPath = '%TARGET_DIR%untimepythonpythonw.exe'; $s.Arguments = '"%TARGET_DIR%applauncher.pyw"'; $s.WorkingDirectory = '%TARGET_DIR%'; $ico = '%TARGET_DIR%approntendassetslauncher.ico'; if (Test-Path $ico) { $s.IconLocation = $ico + ',0' }; $s.Save();"

echo.
echo [OK] Установка успешно завершена!
echo      Ярлык «F-Engineering Launcher» создан на вашем Рабочем столе.
echo.
echo Запуск приложения...
start "" "%TARGET_DIR%untimepythonpythonw.exe" "%TARGET_DIR%applauncher.pyw"
timeout /t 3 >nul
endlocal
'@
[System.IO.File]::WriteAllText((Join-Path $usbRoot "💾_Установить_на_этот_компьютер.cmd"), $installCmd, [System.Text.Encoding]::UTF8)

# Инструкция
$readme = @'
========================================================================
   F-Engineering Launcher v3 — Автономный пакет (USB)
========================================================================

На целевом компьютере НЕ ТРЕБУЕТСЯ ничего устанавливать (ни Python, ни библиотеки).
Всё уже встроено в папку программы!

ВАРИАНТ 1 (Запуск без установки):
Дважды кликните по файлу «🚀_Запуск_Лаунчера.cmd».
Лаунчер сразу запустится прямо с флешки.

ВАРИАНТ 2 (Установка на компьютер в 1 клик):
Дважды кликните по файлу «💾_Установить_на_этот_компьютер.cmd».
Программа скопируется на ПК, создаст ярлык на Рабочем столе и сразу запустится.
После этого флешку можно извлечь.

ВАРИАНТ 3 (Через архив):
Если вы хотите отправить программу коллеге по почте или мессенджеру,
возьмите файл «FEngineering_Launcher_v3_Portable.zip» (78 МБ).
'@
[System.IO.File]::WriteAllText((Join-Path $usbRoot "ИНСТРУКЦИЯ.txt"), $readme, [System.Text.Encoding]::UTF8)
Write-Host "      Корневые файлы созданы." -ForegroundColor Green

Write-Host "[4/4] Проверка готовности флешки..." -ForegroundColor Cyan
$checkRun = Test-Path (Join-Path $usbRoot "🚀_Запуск_Лаунчера.cmd")
$checkInstall = Test-Path (Join-Path $usbRoot "💾_Установить_на_этот_компьютер.cmd")
$checkPy = Test-Path (Join-Path $destFolder "runtime\python\pythonw.exe")

if ($checkRun -and $checkInstall -and $checkPy) {
    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Green
    Write-Host "   ФЛЕШКА УСПЕШНО ПОДГОТОВЛЕНА И ГОТОВА К РАБОТЕ!                      " -ForegroundColor Green
    Write-Host "========================================================================" -ForegroundColor Green
    Write-Host "Диск: $($drive.DeviceId)"
    Write-Host "Что записано на флешку:"
    Write-Host "  1. 🚀_Запуск_Лаунчера.cmd            (мгновенный запуск прямо с флешки)"
    Write-Host "  2. 💾_Установить_на_этот_компьютер.cmd (копирование на ПК + ярлык на столе)"
    Write-Host "  3. FEngineering_Launcher\            (автономная папка с Python и Poppler)"
    Write-Host "  4. FEngineering_Launcher_v3_Portable.zip (архив для отправки коллегам)"
    Write-Host "  5. ИНСТРУКЦИЯ.txt"
    Write-Host ""
    Write-Host "Теперь просто извлеките флешку и вставьте в любой другой компьютер!" -ForegroundColor Cyan
} else {
    Write-Host "Внимание: некоторые файлы не прошли проверку!" -ForegroundColor Red
}
