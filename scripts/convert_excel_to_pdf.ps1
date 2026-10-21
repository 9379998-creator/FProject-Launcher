param(
  [Parameter(Mandatory = $true)]
  [string]$InputPath,

  [Parameter(Mandatory = $true)]
  [string]$OutputPath
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$inputItem = Get-Item -LiteralPath $InputPath
$outputParent = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $outputParent)) {
  New-Item -ItemType Directory -Force -Path $outputParent | Out-Null
}

$excel = $null
$workbook = $null

try {
  $excel = New-Object -ComObject Excel.Application
  $excel.Visible = $false
  $excel.ScreenUpdating = $false
  $excel.DisplayAlerts = $false
  $excel.AskToUpdateLinks = $false
  Start-Sleep -Milliseconds 1500
  if (-not $excel.Ready) {
    throw "Excel сейчас не готов к автоматическому открытию книг. Закройте или завершите стартовый/лицензионный диалог Excel и повторите отображение книги."
  }

  $opened = $false
  $lastOpenError = $null
  for ($attempt = 1; $attempt -le 2; $attempt++) {
    try {
      $workbook = $excel.Workbooks.Open($inputItem.FullName, 0, $true)
      $opened = $true
      break
    }
    catch {
      $lastOpenError = $_
      Start-Sleep -Milliseconds (800 * $attempt)
    }
  }
  if (-not $opened) {
    $openMessage = if ($lastOpenError) { $lastOpenError.Exception.Message } else { "неизвестная ошибка" }
    if ($lastOpenError.Exception.HResult -in @(-2147418111, -2146827286) -or $openMessage -match "0x80010001|0x800AC472|отклон|свойство Open") {
      throw "Excel сейчас не принимает автоматические команды. Закройте или завершите стартовый/лицензионный диалог Excel и повторите отображение книги."
    }
    throw $lastOpenError
  }
  Start-Sleep -Milliseconds 700

  $xlTypePDF = 0
  $xlQualityStandard = 0
  $exported = $false
  $lastError = $null
  for ($attempt = 1; $attempt -le 2; $attempt++) {
    try {
      $workbook.ExportAsFixedFormat($xlTypePDF, $OutputPath, $xlQualityStandard, $true, $false)
      $exported = $true
      break
    }
    catch {
      $lastError = $_
      Start-Sleep -Milliseconds (700 * $attempt)
    }
  }
  if (-not $exported) {
    throw $lastError
  }
}
finally {
  if ($workbook -ne $null) {
    try { $workbook.Close($false) } catch {}
    try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($workbook) | Out-Null } catch {}
  }
  if ($excel -ne $null) {
    try { $excel.Quit() } catch {}
    try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null } catch {}
  }
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}

if (-not (Test-Path -LiteralPath $OutputPath)) {
  throw "Excel не создал PDF: $OutputPath"
}
