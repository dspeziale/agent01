<#
==============================================================================
Sysmon Telemetry - Launcher Sonda di Debug a Video (Windows)
Esecuzione rapida:
  irm https://simei.dsc-italy.app/debug.ps1 | iex
==============================================================================
#>

$ErrorActionPreference = "Continue"

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "   SYSMON TELEMETRY - AVVIO SONDA DI DEBUG A VIDEO       " -ForegroundColor Cyan
Write-Host "==========================================================`n" -ForegroundColor Cyan

# 1. Rileva il miglior interprete Python disponibile
$VenvPy = "C:\Program Files\Sysmon\.venv\Scripts\python.exe"
$PythonExe = $null

if (Test-Path $VenvPy) {
    Write-Host "[1/2] Rilevato ambiente virtuale dedicato Sysmon: $VenvPy" -ForegroundColor Green
    $PythonExe = $VenvPy
} else {
    $SysPy = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($SysPy) {
        Write-Host "[1/2] Rilevato Python di sistema: $($SysPy.Source)" -ForegroundColor Yellow
        $PythonExe = $SysPy.Source
    }
}

if (-not $PythonExe) {
    Write-Host "[ERRORE CRITICO] Nessun interprete Python trovato nel sistema!" -ForegroundColor Red
    Write-Host "Installa Python da https://www.python.org/downloads/ oppure esegui prima l'installer:" -ForegroundColor Yellow
    Write-Host "  irm https://simei.dsc-italy.app/install.ps1 | iex`n" -ForegroundColor Cyan
    return
}

# 2. Download o caricamento script di debug
$ServerUrl = if ($env:SYSMON_SERVER) { $env:SYSMON_SERVER } else { "https://simei.dsc-italy.app" }
$DebugScriptUrl = "$ServerUrl/debug.py"
$LocalScript = "C:\Program Files\Sysmon\debug_probe.py"
$TempScript = Join-Path $env:TEMP "sysmon_debug_probe.py"

$TargetScript = $null

if (Test-Path $LocalScript) {
    $TargetScript = $LocalScript
    Write-Host "[2/2] Utilizzo sonda locale: $LocalScript" -ForegroundColor Green
} else {
    Write-Host "[2/2] Download sonda aggiornata da $DebugScriptUrl..." -ForegroundColor Yellow
    try {
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12 -bor [System.Net.SecurityProtocolType]::Tls13
        Invoke-WebRequest -Uri $DebugScriptUrl -OutFile $TempScript -UseBasicParsing -TimeoutSec 15
        $TargetScript = $TempScript
        Write-Host "  -> Sonda scaricata in $TempScript" -ForegroundColor Green
    } catch {
        Write-Host "  -> [AVVISO] Impossibile scaricare la sonda via Invoke-WebRequest: $_" -ForegroundColor Red
        return
    }
}

Write-Host "`nAvvio esecuzione diagnostica a video...`n" -ForegroundColor Cyan

# 3. Esecuzione interattiva
& $PythonExe $TargetScript $args
