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

$word = $null
$document = $null
$wordPid = $null

try {
  $existingWordPids = @(Get-Process -Name "WINWORD" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
  $word = New-Object -ComObject Word.Application
  $newWordPids = @(Get-Process -Name "WINWORD" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
  $wordPid = ($newWordPids | Where-Object { $_ -notin $existingWordPids } | Select-Object -First 1)

  $word.Visible = $false
  $word.ScreenUpdating = $false
  $word.DisplayAlerts = 0

  $document = $word.Documents.Open($inputItem.FullName, $false, $true)
  $wdFormatPDF = 17
  $document.SaveAs2($OutputPath, $wdFormatPDF)
}
finally {
  if ($document -ne $null) {
    try { $document.Close($false) } catch {}
    try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) | Out-Null } catch {}
  }
  if ($word -ne $null) {
    try { $word.Quit() } catch {}
    try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null } catch {}
  }
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
  if ($wordPid) {
    try {
      $p = Get-Process -Id $wordPid -ErrorAction SilentlyContinue
      if ($p -and -not $p.HasExited) {
        Stop-Process -Id $wordPid -Force -ErrorAction SilentlyContinue
      }
    } catch {}
  }
}

if (-not (Test-Path -LiteralPath $OutputPath)) {
  throw "Word не создал PDF: $OutputPath"
}
