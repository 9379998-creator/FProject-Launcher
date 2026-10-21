$ErrorActionPreference = "Stop"

[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = "python"
if (Test-Path -LiteralPath "C:\Python314\python.exe") {
  $python = "C:\Python314\python.exe"
}

& $python (Join-Path $repoRoot "scripts\check_encoding.py")
