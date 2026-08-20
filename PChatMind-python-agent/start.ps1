#Requires -Version 5.1
<#
.SYNOPSIS
  One-click start for PChatMind full-stack (backend + frontend).

.USAGE
  From project root:
    .\start.ps1
  Or double-click start.bat
#>

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$UiDir = Join-Path $Root "ui"
$BackendPort = 8080
$FrontendPort = 5173
$QwenKey = "sk-ws-H.EDEYPLH.HGXG.MEYCIQCaI0dcxgeKpyhE-zGbl55-0tZhuz-EZX8Vy0H6e-vrMgIhAIzswB3JtB3VLJThVo_4VhPfY689Vtxw-4_UcubTYImM"

function Stop-PortListeners {
    param([int]$Port)
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    } catch {
        $conns = @()
    }
    foreach ($c in @($conns)) {
        $procId = $c.OwningProcess
        if (-not $procId -or $procId -eq 0) { continue }
        try {
            $proc = Get-Process -Id $procId -ErrorAction Stop
            Write-Host "Freeing port $Port (PID $procId / $($proc.ProcessName)) ..." -ForegroundColor Yellow
            Stop-Process -Id $procId -Force -ErrorAction Stop
        } catch {
            Write-Host "Could not stop PID $procId on port $Port : $_" -ForegroundColor DarkYellow
        }
    }
}

function Get-LanIPv4 {
    # 优先无线网卡，其次有线；排除 127/169.254/VMware 虚拟网段
    $candidates = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notlike "127.*" -and
            $_.IPAddress -notlike "169.254.*" -and
            $_.IPAddress -notlike "192.168.245.*" -and
            $_.IPAddress -notlike "192.168.119.*" -and
            $_.PrefixOrigin -ne "WellKnown"
        } |
        Sort-Object @{
            Expression = {
                switch -Regex ($_.InterfaceAlias) {
                    "WLAN|Wi-?Fi|无线" { 0 }
                    "Ethernet|以太网" { 1 }
                    default { 2 }
                }
            }
        }, IPAddress
    if ($candidates) {
        return $candidates[0].IPAddress
    }
    return "127.0.0.1"
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] venv not found: $VenvPython" -ForegroundColor Red
    Write-Host "Create .venv and install requirements.txt first."
    exit 1
}

if (-not (Test-Path (Join-Path $UiDir "package.json"))) {
    Write-Host "[ERROR] frontend dir not found: $UiDir" -ForegroundColor Red
    exit 1
}

$LanIp = Get-LanIPv4

Write-Host "Checking ports $BackendPort / $FrontendPort ..." -ForegroundColor DarkGray
Stop-PortListeners -Port $BackendPort
Stop-PortListeners -Port $FrontendPort
Start-Sleep -Milliseconds 500

$BackendCmd = @"
`$Host.UI.RawUI.WindowTitle = '东盟助手 Backend :$BackendPort'
Set-Location '$Root'
`$env:JCHATMIND_QWEN_API_KEY = '$QwenKey'
`$env:JCHATMIND_QWEN_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
`$env:JCHATMIND_QWEN_MODEL = 'qwen3-max'
Remove-Item Env:JCHATMIND_DEEPSEEK_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:JCHATMIND_ZHIPU_API_KEY -ErrorAction SilentlyContinue
Write-Host 'Backend listening on 0.0.0.0:$BackendPort (LAN: http://${LanIp}:$BackendPort)' -ForegroundColor Cyan
Write-Host 'Model: qwen3-max (通义). DeepSeek / 智谱未启用' -ForegroundColor DarkGray
& '$VenvPython' -m jchatmind_app
`$code = `$LASTEXITCODE
if (`$null -eq `$code) { `$code = 0 }
Write-Host ""
if (`$code -eq 0) {
    Write-Host "Backend stopped (exit code 0). Press any key to close." -ForegroundColor DarkGray
} else {
    Write-Host "Backend stopped (exit code `$code). If you did not close it, check errors above." -ForegroundColor Red
}
`$null = `$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
"@

$FrontendCmd = @"
`$Host.UI.RawUI.WindowTitle = '东盟助手 Frontend :$FrontendPort'
Set-Location '$UiDir'
Write-Host 'Frontend starting (Vite, host 0.0.0.0)...' -ForegroundColor Cyan
Write-Host "LAN URL: http://${LanIp}:$FrontendPort" -ForegroundColor Yellow
npm.cmd run dev -- --host 0.0.0.0 --port $FrontendPort
`$code = `$LASTEXITCODE
if (`$null -eq `$code) { `$code = 0 }
Write-Host ""
if (`$code -eq 0) {
    Write-Host "Frontend stopped (exit code 0). Press any key to close." -ForegroundColor DarkGray
} else {
    Write-Host "Frontend stopped (exit code `$code). Press any key to close." -ForegroundColor Red
}
`$null = `$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
"@

Write-Host "Starting backend and frontend..." -ForegroundColor Green
Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $BackendCmd)
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $FrontendCmd)

Write-Host ""
Write-Host "本机访问:" -ForegroundColor Yellow
Write-Host "  Frontend: http://127.0.0.1:$FrontendPort"
Write-Host "  Backend : http://127.0.0.1:$BackendPort"
Write-Host ""
Write-Host "局域网访问 (同学用这个):" -ForegroundColor Green
Write-Host "  Frontend: http://${LanIp}:$FrontendPort"
Write-Host "  Backend : http://${LanIp}:$BackendPort"
Write-Host ""
Write-Host "说明: 前端页面请用 Frontend 地址；/api 与 /sse 会由 Vite 代理到本机后端。"
Write-Host "若同学打不开，请在 Windows 防火墙放行 TCP $FrontendPort 和 $BackendPort。"
Write-Host "Two windows opened. Close each window (or Ctrl+C) to stop that service."
Write-Host "Do not run start.ps1 twice while services are already running."
Write-Host "Make sure PostgreSQL database jchatmind is running."
