<#
.SYNOPSIS
    Script di installazione e gestione automatica dell'agente Sysmon come servizio di background su Windows.

.DESCRIPTION
    Configura l'ambiente Python (o lo installa se mancante tramite winget), scarica i sorgenti se eseguito da remoto,
    installa le dipendenze in un virtualenv isolato, genera la configurazione config.json e registra
    l'agente nell'Utilità di Pianificazione di Windows (Scheduled Task) ad avvio invisibile e automatico.

.PARAMETER ServerUrl
    L'URL dell'endpoint del server HTTPS (default: https://simei.dsc-italy.app/api/v1/metrics)

.PARAMETER Token
    Token di autenticazione API (opzionale)

.PARAMETER Interval
    Intervallo di invio metriche in secondi (default: 15)

.PARAMETER InstallDir
    Cartella di installazione (default: cartella corrente del repository, o C:\Program Files\Sysmon se eseguito da remoto)

.PARAMETER Status
    Verifica lo stato del servizio e visualizza gli ultimi log

.PARAMETER Uninstall
    Rimuove completamente il servizio Sysmon e le attività pianificate dal sistema
#>

param(
    [string]$ServerUrl = "https://simei.dsc-italy.app/api/v1/metrics",
    [string]$Token = "",
    [int]$Interval = 15,
    [string]$InstallDir = "",
    [switch]$Status,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$TaskName = "SysmonAgent"
$GithubZipUrl = "https://github.com/dspeziale/agent01/archive/refs/heads/main.zip"

# -------------------------------------------------------------
# ELEVAZIONE AMMINISTRATORE (Solo se necessario e possibile)
# -------------------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin -and -not $Status) {
    Write-Host "[INFO] Privilegi di Amministratore raccomandati. Tentativo elevazione UAC..." -ForegroundColor Cyan
    
    $argsList = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    foreach ($key in $PSBoundParameters.Keys) {
        $val = $PSBoundParameters[$key]
        if ($val -is [switch] -and $val.IsPresent) {
            $argsList += " -$key"
        } elseif ($val -isnot [switch]) {
            $argsList += " -$key `"$val`""
        }
    }
    
    try {
        Start-Process powershell.exe -Verb RunAs -ArgumentList $argsList
        exit 0
    } catch {
        Write-Host "  -> Impossibile richiedere elevazione interattiva (ambiente headless/non-interattivo)." -ForegroundColor Yellow
        Write-Host "  -> Continuo con i permessi correnti..." -ForegroundColor Yellow
    }
}

# -------------------------------------------------------------
# RISOLUZIONE CARTELLA DI INSTALLAZIONE
# -------------------------------------------------------------
if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    if ($PSScriptRoot) {
        # Se eseguito da file locale
        $candidateLocal = Resolve-Path (Join-Path $PSScriptRoot "..") -ErrorAction SilentlyContinue
        if ($candidateLocal -and (Test-Path (Join-Path $candidateLocal "sysmon"))) {
            $InstallDir = $candidateLocal.Path
        } elseif (Test-Path (Join-Path $PSScriptRoot "sysmon")) {
            $InstallDir = $PSScriptRoot
        }
    }
    
    if ([string]::IsNullOrWhiteSpace($InstallDir)) {
        # Fallback per esecuzione one-liner da remoto (es. irm ... | iex)
        $InstallDir = "C:\Program Files\Sysmon"
    }
}

# -------------------------------------------------------------
# 1. CONTROLLO STATO (-Status)
# -------------------------------------------------------------
if ($Status) {
    Write-Host "`n=== STATO DEL SERVIZIO SYSMON (WINDOWS) ===" -ForegroundColor Cyan
    $taskInfo = cmd.exe /c "schtasks.exe /Query /TN $TaskName /V /FO LIST 2>nul"
    if ($LASTEXITCODE -eq 0 -and $taskInfo) {
        Write-Host "Attivita' Pianificata ${TaskName}: PRESENTE" -ForegroundColor Green
        $taskInfo | Where-Object { $_ -match "Stato|Last Run|Next Run|State|Comment" } | ForEach-Object { Write-Host "  $_" -ForegroundColor White }
    } else {
        Write-Host "Attivita' Pianificata ${TaskName}: NON REGISTRATA (o non ancora creata)" -ForegroundColor Yellow
    }

    # Verifica processi attivi
    $procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*sysmon*" -or $_.CommandLine -like "*main.py*" }
    if ($procs) {
        Write-Host "`nProcesso Agente in esecuzione: ATTIVO (PID: $($procs.ProcessId -join ', '))" -ForegroundColor Green
    } else {
        Write-Host "`nNessun processo Sysmon attualmente attivo." -ForegroundColor Yellow
    }

    $logPath = Join-Path $InstallDir "sysmon.log"
    if (Test-Path $logPath) {
        Write-Host "`n--- Ultimi log da $logPath ---" -ForegroundColor Cyan
        Get-Content $logPath -Tail 20 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    }
    Write-Host ""
    exit 0
}

# -------------------------------------------------------------
# 2. DISINSTALLAZIONE (-Uninstall)
# -------------------------------------------------------------
if ($Uninstall) {
    Write-Host "`n==========================================================" -ForegroundColor Yellow
    Write-Host "         DISINSTALLAZIONE AGENTE SYSMON (WINDOWS)         " -ForegroundColor Yellow
    Write-Host "==========================================================" -ForegroundColor Yellow
    
    Write-Host "[1/3] Arresto e cancellazione Attivita' Pianificata $TaskName..." -ForegroundColor Cyan
    cmd.exe /c "schtasks.exe /End /TN $TaskName 2>nul" | Out-Null
    cmd.exe /c "schtasks.exe /Delete /TN $TaskName /F 2>nul" | Out-Null

    Write-Host "[2/3] Terminazione di eventuali processi residenti in background..." -ForegroundColor Cyan
    Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*sysmon*" -or $_.CommandLine -like "*main.py*" } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

    $vbsFile = Join-Path $InstallDir "sysmon_service.vbs"
    if (Test-Path $vbsFile) {
        Remove-Item -Path $vbsFile -Force -ErrorAction SilentlyContinue
    }

    Write-Host "[3/3] Pulizia completata." -ForegroundColor Cyan
    Write-Host "[OK] Agente Sysmon disinstallato con successo dal sistema!`n" -ForegroundColor Green
    exit 0
}

# -------------------------------------------------------------
# 3. INSTALLAZIONE COMPLETA
# -------------------------------------------------------------
Clear-Host
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       SYSMON AGENT - INSTALLATORE AUTOMATICO WINDOWS      " -ForegroundColor Cyan
Write-Host "==========================================================`n" -ForegroundColor Cyan

# 1. Verifica / Installazione di Python
Write-Host "[1/5] Verifica interprete Python..." -ForegroundColor Yellow
$PythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue

if (-not $PythonCmd) {
    Write-Host "  -> Python non rilevato nel PATH di sistema. Tentativo di installazione automatica via winget..." -ForegroundColor Yellow
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($winget) {
        try {
            & winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
            Start-Sleep -Seconds 3
            # Ricarica PATH per la sessione corrente
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            $PythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
        } catch {
            Write-Host "  -> Installazione winget non riuscita." -ForegroundColor Red
        }
    }
}

if (-not $PythonCmd) {
    Write-Host "`n[ERRORE] Python non e' installato o non e' presente nella variabile PATH!" -ForegroundColor Red
    Write-Host "1. Scarica Python 3 da: https://www.python.org/downloads/" -ForegroundColor White
    Write-Host "2. Durante l'installazione seleziona la casella: 'Add python.exe to PATH'" -ForegroundColor Yellow
    Write-Host "3. Riavvia questo script al termine dell'installazione.`n" -ForegroundColor White
    Read-Host "Premi INVIO per uscire..."
    exit 1
}

$pyVersion = & python.exe --version
Write-Host "  -> $pyVersion (OK)" -ForegroundColor Green

# 2. Predisposizione cartella e sorgenti
Write-Host "`n[2/5] Predisposizione cartella applicazione in $InstallDir..." -ForegroundColor Yellow
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

$hasLocalSources = (Test-Path (Join-Path $InstallDir "sysmon")) -and (Test-Path (Join-Path $InstallDir "main.py"))
if (-not $hasLocalSources) {
    Write-Host "  -> Download sorgenti aggiornati da GitHub ($GithubZipUrl)..." -ForegroundColor Cyan
    $tempZip = Join-Path $env:TEMP "sysmon_source.zip"
    $tempExtract = Join-Path $env:TEMP "sysmon_extracted"
    
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12 -bor [System.Net.SecurityProtocolType]::Tls13
    Invoke-WebRequest -Uri $GithubZipUrl -OutFile $tempZip -UseBasicParsing
    
    if (Test-Path $tempExtract) { Remove-Item -Path $tempExtract -Recurse -Force }
    Expand-Archive -Path $tempZip -DestinationPath $tempExtract -Force
    
    $extractedRoot = Get-ChildItem -Path $tempExtract -Directory | Select-Object -First 1
    if ($extractedRoot -and (Test-Path (Join-Path $extractedRoot.FullName "sysmon"))) {
        Copy-Item -Path (Join-Path $extractedRoot.FullName "sysmon") -Destination $InstallDir -Recurse -Force
        Copy-Item -Path (Join-Path $extractedRoot.FullName "main.py") -Destination $InstallDir -Force
        if (Test-Path (Join-Path $extractedRoot.FullName "requirements-agent.txt")) {
            Copy-Item -Path (Join-Path $extractedRoot.FullName "requirements-agent.txt") -Destination $InstallDir -Force
        }
        Write-Host "  -> Sorgenti estratti in $InstallDir con successo." -ForegroundColor Green
    }
    Remove-Item -Path $tempZip -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
}

# 3. Creazione Ambiente Virtuale (.venv) e Installazione Dipendenze
Write-Host "`n[3/5] Configurazione ambiente virtuale isolato (.venv)..." -ForegroundColor Yellow
$VenvDir = Join-Path $InstallDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "  -> Creazione virtual environment in $VenvDir..." -ForegroundColor Cyan
    & python.exe -m venv $VenvDir
}

Write-Host "  -> Installazione pacchetti essenziali (psutil, requests)..." -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade --no-warn-script-location pip | Out-Null
$ReqFile = Join-Path $InstallDir "requirements-agent.txt"
if (Test-Path $ReqFile) {
    & $VenvPip install --no-warn-script-location -r $ReqFile | Out-Null
} else {
    & $VenvPip install --no-warn-script-location "psutil>=5.9.0" "requests>=2.31.0" | Out-Null
}
Write-Host "  -> Dipendenze Python installate con successo nel virtualenv." -ForegroundColor Green

# 4. Creazione File config.json
Write-Host "`n[4/5] Configurazione parametri operativi (config.json)..." -ForegroundColor Yellow
$ConfigFile = Join-Path $InstallDir "config.json"
$BufferDbPath = Join-Path $InstallDir "sysmon_buffer.db"
$LogFilePath = Join-Path $InstallDir "sysmon.log"

$configObj = @{
    server_url = $ServerUrl
    api_key = $Token
    auth_type = if ($Token) { "Bearer" } else { "None" }
    interval_seconds = [double]$Interval
    verify_ssl = $true
    offline_buffer_enabled = $true
    offline_buffer_db_path = $BufferDbPath
    include_processes = $true
    top_processes_count = 10
    include_disk_io = $true
    include_net_io = $true
    include_network_interfaces = $true
    log_level = "INFO"
    log_file = $LogFilePath
}

$configJson = $configObj | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($ConfigFile, $configJson, [System.Text.Encoding]::UTF8)

Write-Host "  -> Server di destinazione: $ServerUrl" -ForegroundColor Cyan
Write-Host "  -> Intervallo campionamento: ogni ${Interval}s" -ForegroundColor Cyan
Write-Host "  -> File configurazione generato: $ConfigFile" -ForegroundColor Gray

# 5. Registrazione Servizio / Attività Pianificata (Avvio automatico al boot)
Write-Host "`n[5/5] Registrazione Attivita' Pianificata Windows ($TaskName)..." -ForegroundColor Yellow

$LauncherVbs = Join-Path $InstallDir "sysmon_service.vbs"
$MainPy = Join-Path $InstallDir "main.py"

# Script VBS per eseguire l'interprete Python senza mostrare alcuna finestra console o popup
$VbsContent = "CreateObject(`"Wscript.Shell`").Run `"`"`"$VenvPython`"`" `"`"$MainPy`"`" --config `"`"$ConfigFile`"`"`, 0, False"
[System.IO.File]::WriteAllText($LauncherVbs, $VbsContent, [System.Text.Encoding]::ASCII)

# Rimuovi eventuale task precedente
cmd.exe /c "schtasks.exe /End /TN $TaskName 2>nul" | Out-Null
cmd.exe /c "schtasks.exe /Delete /TN $TaskName /F 2>nul" | Out-Null

# Crea il nuovo task con privilegi massimi ad avvio macchina (ONSTART come SYSTEM)
$TaskCommand = "wscript.exe `"$LauncherVbs`""
cmd.exe /c "schtasks.exe /Create /TN $TaskName /TR `"$TaskCommand`" /SC ONSTART /RU SYSTEM /RL HIGHEST /F 2>nul" | Out-Null

if ($LASTEXITCODE -ne 0) {
    # Fallback su ONLOGON se il contesto SYSTEM e' ristretto da policy aziendali
    Write-Host "  -> Fallback trigger su accesso utente (ONLOGON)..." -ForegroundColor Yellow
    cmd.exe /c "schtasks.exe /Create /TN $TaskName /TR `"$TaskCommand`" /SC ONLOGON /RL HIGHEST /F" | Out-Null
}

# Avvia immediatamente l'attività
cmd.exe /c "schtasks.exe /Run /TN $TaskName 2>nul" | Out-Null
Start-Sleep -Seconds 2

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "    INSTALLAZIONE COMPLETATA CON SUCCESSO SU WINDOWS!      " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "L'agente Sysmon e' ora attivo e partira' automaticamente ad ogni avvio del PC." -ForegroundColor White
Write-Host "  • Attivita' Pianificata:  $TaskName" -ForegroundColor Gray
Write-Host "  • Directory di lavoro:    $InstallDir" -ForegroundColor Gray
Write-Host "  • Log in tempo reale:     $LogFilePath" -ForegroundColor Gray
Write-Host "  • Dashboard Web Flotta:   https://simei.dsc-italy.app/" -ForegroundColor Cyan
Write-Host "`nComandi di gestione rapida:" -ForegroundColor Yellow
Write-Host "  • Verifica stato: powershell -File `"$PSCommandPath`" -Status" -ForegroundColor Gray
Write-Host "  • Disinstalla:    powershell -File `"$PSCommandPath`" -Uninstall`n" -ForegroundColor Gray
