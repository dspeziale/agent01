<#
==============================================================================
Pulsar Telemetry - Launcher Sonda di Debug a Video (Windows)
Esecuzione rapida:
  irm https://simei.dsc-italy.app/debug.ps1 | iex
==============================================================================
#>

$ErrorActionPreference = "Continue"

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "   PULSAR TELEMETRY - AVVIO SONDA DI DEBUG A VIDEO       " -ForegroundColor Cyan
Write-Host "==========================================================`n" -ForegroundColor Cyan

# 1. Rileva il miglior interprete Python disponibile
$PulsarVenvPy = "C:\Program Files\Pulsar\.venv\Scripts\python.exe"
$SysmonVenvPy = "C:\Program Files\Sysmon\.venv\Scripts\python.exe"
$PythonExe = $null

if (Test-Path $PulsarVenvPy) {
    Write-Host "[1/2] Rilevato ambiente virtuale dedicato Pulsar: $PulsarVenvPy" -ForegroundColor Green
    $PythonExe = $PulsarVenvPy
} elseif (Test-Path $SysmonVenvPy) {
    Write-Host "[1/2] Rilevato ambiente virtuale legacy Sysmon: $SysmonVenvPy" -ForegroundColor Yellow
    $PythonExe = $SysmonVenvPy
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
$ServerUrl = if ($env:PULSAR_SERVER) { $env:PULSAR_SERVER } elseif ($env:SYSMON_SERVER) { $env:SYSMON_SERVER } else { "https://simei.dsc-italy.app" }
$DebugScriptUrl = "$ServerUrl/debug.py"
$LocalPulsarScript = "C:\Program Files\Pulsar\debug_probe.py"
$LocalSysmonScript = "C:\Program Files\Sysmon\debug_probe.py"
$TempScript = Join-Path $env:TEMP "pulsar_debug_probe.py"

$TargetScript = $null

if (Test-Path $LocalPulsarScript) {
    $TargetScript = $LocalPulsarScript
    Write-Host "[2/2] Utilizzo sonda locale Pulsar: $LocalPulsarScript" -ForegroundColor Green
} elseif (Test-Path $LocalSysmonScript) {
    $TargetScript = $LocalSysmonScript
    Write-Host "[2/2] Utilizzo sonda locale Sysmon: $LocalSysmonScript" -ForegroundColor Yellow
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
