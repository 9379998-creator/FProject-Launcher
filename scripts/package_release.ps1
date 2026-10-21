$ErrorActionPreference = "Stop"

[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$repoRoot = Split-Path -Parent $PSScriptRoot
$distDir = Join-Path $repoRoot "dist"
$stamp = Get-Date -Format "yyyy-MM-dd"
$zipPath = Join-Path $distDir "FEngineering_Launcher_v3-portable-$stamp.zip"
$stageDir = Join-Path $env:TEMP "launcher-portable-$stamp"

if (Test-Path -LiteralPath $stageDir) {
  Remove-Item -LiteralPath $stageDir -Recurse -Force
}
if (Test-Path -LiteralPath $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}

Write-Host "Building portable Launcher v3 release"
Write-Host "  repo:   $repoRoot"
Write-Host "  stage:  $stageDir"
Write-Host "  output: $zipPath"

function Copy-Tree {
  param(
    [Parameter(Mandatory = $true)][string]$Source,
    [Parameter(Mandatory = $true)][string]$Destination
  )
  if (-not (Test-Path -LiteralPath $Source)) {
    throw "Source does not exist: $Source"
  }
  New-Item -ItemType Directory -Force -Path $Destination | Out-Null
  Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
    if ($_.PSIsContainer) {
      $skip = $_.Name -in @("__pycache__", ".venv", "venv", "node_modules", "dist", "build", "renders", "output")
      if (-not $skip) {
        Copy-Tree -Source $_.FullName -Destination (Join-Path $Destination $_.Name)
      }
    }
    else {
      if ($_.Name -notlike "*.pyc") {
        Copy-Item -LiteralPath $_.FullName -Destination $Destination
      }
    }
  }
}

# --- app/ ---
Copy-Tree -Source (Join-Path $repoRoot "app") -Destination (Join-Path $stageDir "app")

# --- scripts/ ---
Copy-Tree -Source (Join-Path $repoRoot "scripts") -Destination (Join-Path $stageDir "scripts")

# --- docs/ ---
Copy-Tree -Source (Join-Path $repoRoot "docs") -Destination (Join-Path $stageDir "docs")

# --- tests/ and tools/ ---
if (Test-Path -LiteralPath (Join-Path $repoRoot "tests")) {
  Copy-Tree -Source (Join-Path $repoRoot "tests") -Destination (Join-Path $stageDir "tests")
}
if (Test-Path -LiteralPath (Join-Path $repoRoot "tools")) {
  Copy-Tree -Source (Join-Path $repoRoot "tools") -Destination (Join-Path $stageDir "tools")
}

# --- root meta files and launch scripts ---
foreach ($name in @("README.md", "AGENTS.md", ".gitignore", ".editorconfig", "requirements.txt")) {
  $src = Join-Path $repoRoot $name
  if (Test-Path -LiteralPath $src) {
    Copy-Item -LiteralPath $src -Destination $stageDir
  }
}
Get-ChildItem -LiteralPath $repoRoot -Filter "*.cmd" -File | ForEach-Object {
  Copy-Item -LiteralPath $_.FullName -Destination $stageDir
}

# --- runtime skeleton: only manifests + portable poppler, no caches/logs ---
$runtimeDir = Join-Path $stageDir "runtime"
New-Item -ItemType Directory -Force -Path (Join-Path $runtimeDir "cache") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $runtimeDir "logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $runtimeDir "bench") | Out-Null

$manifestsSource = Join-Path $repoRoot "runtime\manifests"
if (Test-Path -LiteralPath $manifestsSource) {
  New-Item -ItemType Directory -Force -Path (Join-Path $runtimeDir "manifests") | Out-Null
  Get-ChildItem -LiteralPath $manifestsSource -Force -File | Where-Object { $_.Name -ne ".gitkeep" } | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $runtimeDir "manifests")
  }
}

# Portable poppler from the codex runtime cache.
$popplerSource = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler"
if (Test-Path -LiteralPath $popplerSource) {
  Copy-Tree -Source $popplerSource -Destination (Join-Path $runtimeDir "tools\poppler")
  Write-Host "  poppler: bundled from $popplerSource"
}
else {
  Write-Host "  poppler: NOT FOUND in codex cache; portable PDF preview will need poppler on PATH"
}

# --- zip ---
New-Item -ItemType Directory -Force -Path $distDir | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($stageDir, $zipPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)

Remove-Item -LiteralPath $stageDir -Recurse -Force

$sizeMB = [math]::Round((Get-Item -LiteralPath $zipPath).Length / 1MB, 1)
Write-Host "Done: $zipPath ($sizeMB MB)"

Write-Host ""
Write-Host "Установка на целевом компьютере:"
Write-Host "  1. Распакуйте архив в C:\FEngineering_Launcher_v3 (или любую другую папку)."
Write-Host "  2. Запустите SETUP.cmd — мастер проверит систему, установит библиотеки"
Write-Host "     и создаст ярлык на Рабочем столе."
Write-Host "  3. Запускайте лаунчер по клику на ярлык на Рабочем столе!"