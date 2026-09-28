<#
==============================================================================
Sysmon Agent - Remote Installer per Windows
Da eseguire in PowerShell come Amministratore

Comando one-liner:
  irm https://simei.dsc-italy.app/install.ps1 | iex
Oppure:
  Invoke-RestMethod https://simei.dsc-italy.app/install.ps1 | Invoke-Expression
==============================================================================
#>

$ErrorActionPreference = "Stop"

# Parametri operativi
$ServerUrl = if ($env:SYSMON_SERVER) { $env:SYSMON_SERVER } else { "https://simei.dsc-italy.app" }
$MetricsUrl = "$ServerUrl/api/v1/metrics"
$DownloadUrl = "$ServerUrl/download/agent.zip"
$FallbackZipUrl = "https://github.com/dspeziale/agent01/archive/refs/heads/main.zip"
$InstallDir = "C:\Program Files\Sysmon"
$TaskName = "SysmonAgent"
$Interval = 15

Clear-Host
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   SYSMON AGENT - INSTALLAZIONE REMOTA WINDOWS (Admin)    " -ForegroundColor Cyan
Write-Host "==========================================================`n" -ForegroundColor Cyan

# 1. Verifica privilegi di Amministratore
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERRORE CRITICO] Questo script richiede privilegi di Amministratore!" -ForegroundColor Red
    Write-Host "`nCome procedere:" -ForegroundColor Yellow
    Write-Host "1. Fai clic destro su PowerShell o Windows Terminal" -ForegroundColor White
    Write-Host "2. Clicca su 'Esegui come amministratore'" -ForegroundColor White
    Write-Host "3. Incolla ed esegui il comando:" -ForegroundColor White
    Write-Host "   irm $ServerUrl/install.ps1 | iex`n" -ForegroundColor Cyan
    return
}

# 2. Verifica / Installazione di Python
Write-Host "[1/5] Verifica interprete Python..." -ForegroundColor Yellow
$PythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue

if (-not $PythonCmd) {
    Write-Host "  -> Python non rilevato nel PATH. Tentativo installazione automatica con winget..." -ForegroundColor Yellow
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($winget) {
        try {
            & winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
            Start-Sleep -Seconds 3
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            $PythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
        } catch {
            Write-Host "  -> Impossibile installare Python via winget." -ForegroundColor Red
        }
    }
}

if (-not $PythonCmd) {
    Write-Host "`n[ERRORE] Python non e' installato o non e' nel PATH!" -ForegroundColor Red
    Write-Host "Scarica e installa Python da: https://www.python.org/downloads/" -ForegroundColor White
    Write-Host "IMPORTANTE: Spunta 'Add python.exe to PATH' durante l'installazione.`n" -ForegroundColor Yellow
    return
}
$pyVer = & python.exe --version
Write-Host "  -> Rilevato: $pyVer (OK)" -ForegroundColor Green

# 3. Download bundle agente dal server
Write-Host "`n[2/5] Download agente telemetria da $ServerUrl..." -ForegroundColor Yellow
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

$tempZip = Join-Path $env:TEMP "sysmon_remote_agent.zip"
$tempExtract = Join-Path $env:TEMP "sysmon_remote_extract"
if (Test-Path $tempExtract) { Remove-Item -Path $tempExtract -Recurse -Force -ErrorAction SilentlyContinue }

[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12 -bor [System.Net.SecurityProtocolType]::Tls13

$downloadSuccess = $false
try {
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $tempZip -UseBasicParsing -TimeoutSec 30
    $downloadSuccess = $true
} catch {
    Write-Host "  -> Download dal server primario non riuscito, provo mirror GitHub..." -ForegroundColor Yellow
    try {
        Invoke-WebRequest -Uri $FallbackZipUrl -OutFile $tempZip -UseBasicParsing -TimeoutSec 30
        $downloadSuccess = $true
    } catch {
        Write-Host "  -> [ERRORE] Impossibile scaricare l'agente." -ForegroundColor Red
        return
    }
}

Expand-Archive -Path $tempZip -DestinationPath $tempExtract -Force
Remove-Item -Path $tempZip -Force -ErrorAction SilentlyContinue

# Copia i file nella cartella di destinazione
if (Test-Path (Join-Path $tempExtract "sysmon")) {
    Copy-Item -Path (Join-Path $tempExtract "sysmon") -Destination $InstallDir -Recurse -Force
    Copy-Item -Path (Join-Path $tempExtract "main.py") -Destination $InstallDir -Force
    if (Test-Path (Join-Path $tempExtract "requirements-agent.txt")) {
        Copy-Item -Path (Join-Path $tempExtract "requirements-agent.txt") -Destination $InstallDir -Force
    }
} else {
    $subDir = Get-ChildItem -Path $tempExtract -Directory | Select-Object -First 1
    if ($subDir -and (Test-Path (Join-Path $subDir.FullName "sysmon"))) {
        Copy-Item -Path (Join-Path $subDir.FullName "sysmon") -Destination $InstallDir -Recurse -Force
        Copy-Item -Path (Join-Path $subDir.FullName "main.py") -Destination $InstallDir -Force
        if (Test-Path (Join-Path $subDir.FullName "requirements-agent.txt")) {
            Copy-Item -Path (Join-Path $subDir.FullName "requirements-agent.txt") -Destination $InstallDir -Force
        }
    }
}
Remove-Item -Path $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "  -> File dell'agente posizionati in $InstallDir" -ForegroundColor Green

# 4. Ambiente virtuale (.venv) e dipendenze
Write-Host "`n[3/5] Configurazione ambiente virtuale isolato (.venv)..." -ForegroundColor Yellow
$VenvDir = Join-Path $InstallDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

if (-not (Test-Path $VenvPython)) {
    & python.exe -m venv $VenvDir
}

& $VenvPython -m pip install --upgrade --no-warn-script-location pip | Out-Null
$ReqFile = Join-Path $InstallDir "requirements-agent.txt"
if (Test-Path $ReqFile) {
    & $VenvPip install --no-warn-script-location -r $ReqFile | Out-Null
} else {
    & $VenvPip install --no-warn-script-location "psutil>=5.9.0" "requests>=2.31.0" | Out-Null
}
Write-Host "  -> Dipendenze psutil e requests installate con successo." -ForegroundColor Green

# 5. Generazione config.json
Write-Host "`n[4/5] Configurazione parametri operativi (config.json)..." -ForegroundColor Yellow
$ConfigFile = Join-Path $InstallDir "config.json"
$BufferDbPath = Join-Path $InstallDir "sysmon_buffer.db"
$LogFilePath = Join-Path $InstallDir "sysmon.log"

$configObj = @{
    server_url = $MetricsUrl
    api_key = ""
    auth_type = "None"
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
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($ConfigFile, $configJson, $utf8NoBom)
Write-Host "  -> Endpoint metriche: $MetricsUrl" -ForegroundColor Cyan
Write-Host "  -> Frequenza invio: ogni ${Interval}s" -ForegroundColor Cyan

# 4.1 Copia / Download sonda di debug
if (Test-Path (Join-Path $tempExtract "debug_probe.py")) {
    Copy-Item -Path (Join-Path $tempExtract "debug_probe.py") -Destination $InstallDir -Force
} else {
    try {
        Invoke-WebRequest -Uri "$ServerUrl/debug.py" -OutFile (Join-Path $InstallDir "debug_probe.py") -UseBasicParsing -TimeoutSec 10 -ErrorAction SilentlyContinue
    } catch {}
}

# 5. Test di invio iniziale (--once)
Write-Host "`n[5/6] Test di connessione e primo invio telemetria (--once)..." -ForegroundColor Yellow
$testResult = & "$VenvDir\Scripts\python.exe" "$InstallDir\main.py" --config "$ConfigFile" --once 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  -> Primo pacchetto telemetrico inviato con successo al server!" -ForegroundColor Green
} else {
    Write-Host "  -> [AVVISO] Invio telemetria iniziale non riuscito (exit code: $LASTEXITCODE):" -ForegroundColor Yellow
    if ($testResult) {
        $testResult | ForEach-Object { Write-Host "     $_" -ForegroundColor Yellow }
    }
    Write-Host "  -> Puoi diagnosticare a video cosa accade eseguendo: irm $ServerUrl/debug.ps1 | iex" -ForegroundColor Cyan
}

# 6. Registrazione Attività Pianificata (Avvio automatico invisibile)
Write-Host "`n[6/6] Registrazione Attivita' Pianificata ($TaskName)..." -ForegroundColor Yellow
$VenvPythonW = Join-Path $VenvDir "Scripts\pythonw.exe"
if (-not (Test-Path $VenvPythonW)) { $VenvPythonW = $VenvPython }
$MainPy = Join-Path $InstallDir "main.py"

# Termina eventuali istanze precedenti
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*main.py*" -and $_.CommandLine -like "*Sysmon*" } | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

$registered = $false
if (Get-Command Register-ScheduledTask -ErrorAction SilentlyContinue) {
    try {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
        
        $action = New-ScheduledTaskAction -Execute $VenvPythonW -Argument "`"$MainPy`" --config `"$ConfigFile`"" -WorkingDirectory $InstallDir
        
        # Trigger multipli per garantire che la sonda sia sempre attiva:
        # 1. Al boot del sistema
        # 2. Al logon utente
        # 3. Watchdog ogni 5 minuti: grazie a 'MultipleInstances IgnoreNew', se l'agente è già attivo non fa nulla, se è caduto lo riavvia subito
        $triggerStartup = New-ScheduledTaskTrigger -AtStartup
        $triggerLogon = New-ScheduledTaskTrigger -AtLogOn
        $triggerWatchdog = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 9999)
        $triggers = @($triggerStartup, $triggerLogon, $triggerWatchdog)

        $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
        
        # Impostazioni di massima affidabilità:
        # - Non fermare su batteria
        # - Non fermare al termine dell'idle (DontStopOnIdleEnd)
        # - Riavvio automatico fino a 999 volte in caso di interruzione (RestartCount 999, intervallo 1 minuto)
        # - Nessun limite di esecuzione forzata (ExecutionTimeLimit Zero)
        # - Ignora nuove istanze se già attivo (MultipleInstances IgnoreNew)
        $settings = New-ScheduledTaskSettingsSet `
            -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries `
            -DontStopOnIdleEnd `
            -StartWhenAvailable `
            -RestartCount 999 `
            -RestartInterval (New-TimeSpan -Minutes 1) `
            -ExecutionTimeLimit ([TimeSpan]::Zero) `
            -MultipleInstances IgnoreNew `
            -Priority 4
            
        $taskObj = New-ScheduledTask -Action $action -Trigger $triggers -Principal $principal -Settings $settings
        Register-ScheduledTask -TaskName $TaskName -InputObject $taskObj -Force -ErrorAction Stop | Out-Null
        $registered = $true
    } catch {
        try {
            # Fallback se la policy locale limita SYSTEM: usa gruppo Administrators
            $principalLogon = New-ScheduledTaskPrincipal -GroupId "BUILTIN\Administrators" -RunLevel Highest
            $taskObj = New-ScheduledTask -Action $action -Trigger $triggers -Principal $principalLogon -Settings $settings
            Register-ScheduledTask -TaskName $TaskName -InputObject $taskObj -Force -ErrorAction Stop | Out-Null
            $registered = $true
        } catch {
            Write-Host "  -> Registrazione cmdlet fallita, utilizzo fallback schtasks..." -ForegroundColor Yellow
        }
    }
}

# Fallback con schtasks.exe (usando ShortPath 8.3 privo di spazi)
if (-not $registered) {
    try {
        cmd.exe /c "schtasks.exe /End /TN $TaskName 2>nul" | Out-Null
        cmd.exe /c "schtasks.exe /Delete /TN $TaskName /F 2>nul" | Out-Null
        
        $fso = New-Object -ComObject Scripting.FileSystemObject
        $shortPy = if (Test-Path $VenvPythonW) { $fso.GetFile($VenvPythonW).ShortPath } else { $VenvPythonW }
        $shortMain = if (Test-Path $MainPy) { $fso.GetFile($MainPy).ShortPath } else { $MainPy }
        $shortCfg = if (Test-Path $ConfigFile) { $fso.GetFile($ConfigFile).ShortPath } else { $ConfigFile }
        
        & schtasks.exe /Create /TN $TaskName /TR "`"$shortPy`" `"$shortMain`" --config `"$shortCfg`"" /SC ONSTART /RU "SYSTEM" /RL HIGHEST /F 2>$null
        & schtasks.exe /Create /TN "${TaskName}_Watchdog" /TR "`"$shortPy`" `"$shortMain`" --config `"$shortCfg`"" /SC MINUTE /MO 5 /RU "SYSTEM" /RL HIGHEST /F 2>$null
    } catch {}
}

# Avvio immediato tramite Task Scheduler
if (Get-Command Start-ScheduledTask -ErrorAction SilentlyContinue) {
    Start-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue | Out-Null
} else {
    cmd.exe /c "schtasks.exe /Run /TN $TaskName 2>nul" | Out-Null
}

# Garanzia di avvio immediato: se Task Scheduler ritarda l'esecuzione, avvia subito il processo in background
Start-Sleep -Seconds 2
$runningProc = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*main.py*" -and $_.CommandLine -like "*Sysmon*" }
if (-not $runningProc) {
    Start-Process -FilePath $VenvPythonW -ArgumentList "`"$MainPy`" --config `"$ConfigFile`"" -WorkingDirectory $InstallDir -WindowStyle Hidden
}

# Diagnostica e verifica in tempo reale
Write-Host "`n[Verifica] Controllo operativita' agente e prima trasmissione..." -ForegroundColor Yellow
Start-Sleep -Seconds 4

$activeProc = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*main.py*" -and $_.CommandLine -like "*Sysmon*" }
if ($activeProc) {
    Write-Host "  -> Agente Sysmon in esecuzione con PID: $($activeProc.ProcessId -join ', ')" -ForegroundColor Green
} else {
    Write-Host "  -> [ATTENZIONE] Il processo non risulta ancora visibile tra i processi attivi." -ForegroundColor Yellow
}

if (Test-Path $LogFilePath) {
    Write-Host "`n--- Ultimi log registrati da $LogFilePath ---" -ForegroundColor Cyan
    Get-Content $LogFilePath -Tail 6 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "    INSTALLAZIONE COMPLETATA CON SUCCESSO SU WINDOWS!      " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "L'agente telemetria e' ora operativo in background e partira' ad ogni boot." -ForegroundColor White
Write-Host "  • Dashboard Web:         $ServerUrl" -ForegroundColor Cyan
Write-Host "  • Cartella installazione: $InstallDir" -ForegroundColor Gray
Write-Host "  • File di Log:           $LogFilePath" -ForegroundColor Gray
Write-Host "  • Attivita' Pianificata: $TaskName" -ForegroundColor Gray
Write-Host "  • Sonda di Debug a video: irm $ServerUrl/debug.ps1 | iex" -ForegroundColor Yellow
Write-Host "==========================================================`n" -ForegroundColor Green
