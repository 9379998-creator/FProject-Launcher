$ErrorActionPreference = "Stop"

# Запуск лаунчера как приложения Windows: без консоли, в отдельном окне.
# Сервер запускается в фоне и обслуживает окно лаунчера.
$repoRoot = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repoRoot "app\backend\server.py"

function Test-ServerHealthy {
  param([int]$Port)
  try {
    # Быстрая проверка TCP подключения (200 мс), чтобы не зависать на портах в состоянии zombie
    $tcp = New-Object System.Net.Sockets.TcpClient
    $iar = $tcp.BeginConnect("127.0.0.1", $Port, $null, $null)
    if (-not $iar.AsyncWaitHandle.WaitOne(200)) {
      $tcp.Close()
      return $false
    }
    $tcp.Close()

    $req = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:$Port/api/health")
    $req.Timeout = 1000
    $req.Method = "GET"
    $resp = $req.GetResponse()
    $status = [int]$resp.StatusCode
    $resp.Close()
    return ($status -eq 200)
  } catch {
    return $false
  }
}

function Test-PortFree {
  param([int]$Port)
  try {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    $listener.Start()
    $listener.Stop()
    return $true
  } catch {
    return $false
  }
}

$targetPort = $null
$serverProc = $null

# 1. Если сервер уже запущен и отвечает по HTTP /api/health — используем его
foreach ($p in 8780..8789) {
  if (Test-ServerHealthy -Port $p) {
    $targetPort = $p
    break
  }
}

# 2. Если нет активного сервера — ищем первый свободный порт
if (-not $targetPort) {
  foreach ($p in 8780..8789) {
    if (Test-PortFree -Port $p) {
      $targetPort = $p
      break
    }
  }
}

if (-not $targetPort) {
  $targetPort = 8781
}

# 3. Если сервер на targetPort ещё не поднят — запускаем его скрыто
if (-not (Test-ServerHealthy -Port $targetPort)) {
  $portablePyw = Join-Path $repoRoot "runtime\python\pythonw.exe"
  $portablePy = Join-Path $repoRoot "runtime\python\python.exe"
  $pythonw = $null
  if (Test-Path -LiteralPath $portablePyw) {
    $pythonw = $portablePyw
  } elseif (Test-Path -LiteralPath $portablePy) {
    $pythonw = $portablePy
  } elseif (Test-Path -LiteralPath "C:\Python314\pythonw.exe") {
    $pythonw = "C:\Python314\pythonw.exe"
  } else {
    $pywCmd = Get-Command "pythonw.exe" -ErrorAction SilentlyContinue
    if ($pywCmd) {
      $pythonw = $pywCmd.Source
    } else {
      $pyCmd = Get-Command "python.exe" -ErrorAction SilentlyContinue
      if ($pyCmd) {
        $pythonw = $pyCmd.Source
      } else {
        $pythonw = "python.exe"
      }
    }
  }

  $startParams = @{
    FilePath         = $pythonw
    ArgumentList     = "`"$backend`" --port $targetPort"
    WorkingDirectory = $repoRoot
    WindowStyle      = 'Hidden'
    PassThru         = $true
  }
  $serverProc = Start-Process @startParams
  $deadline = (Get-Date).AddSeconds(20)
  while ((Get-Date) -lt $deadline) {
    if (Test-ServerHealthy -Port $targetPort) { break }
    Start-Sleep -Milliseconds 300
    $serverProc.Refresh()
    if ($serverProc.HasExited) { exit 1 }
  }
}

$url = "http://127.0.0.1:$targetPort/"

$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if (-not (Test-Path -LiteralPath $edge)) {
  $edge = "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
}
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$profile = Join-Path $env:LOCALAPPDATA "FEngineeringLauncher\AppProfile"
New-Item -ItemType Directory -Path $profile -Force | Out-Null

if (Test-Path -LiteralPath $edge) {
  & $edge --app=$url --user-data-dir="$profile" --no-first-run
} elseif (Test-Path -LiteralPath $chrome) {
  & $chrome --app=$url --user-data-dir="$profile" --no-first-run
} else {
  Start-Process $url
}

