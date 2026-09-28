$InstallDir = "C:\Program Files\Sysmon"
$LauncherVbs = Join-Path $InstallDir "sysmon_service.vbs"
$TaskName = "SysmonAgent"

Write-Host "Creating task using modern Register-ScheduledTask..."
$registered = $false

if (Get-Command Register-ScheduledTask -ErrorAction SilentlyContinue) {
    try {
        $action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$LauncherVbs`""
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 0)
        $taskObj = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings
        
        Register-ScheduledTask -TaskName $TaskName -InputObject $taskObj -Force -ErrorAction Stop | Out-Null
        $registered = $true
        Write-Host "Successfully registered with SYSTEM via Register-ScheduledTask!"
    } catch {
        Write-Host "SYSTEM registration failed ($_). Trying with Administrators/AtLogon..."
        try {
            $triggerLogon = New-ScheduledTaskTrigger -AtLogOn
            $principalLogon = New-ScheduledTaskPrincipal -GroupId "BUILTIN\Administrators" -RunLevel Highest
            $taskObj = New-ScheduledTask -Action $action -Trigger $triggerLogon -Principal $principalLogon -Settings $settings
            Register-ScheduledTask -TaskName $TaskName -InputObject $taskObj -Force -ErrorAction Stop | Out-Null
            $registered = $true
            Write-Host "Successfully registered with Administrators via Register-ScheduledTask!"
        } catch {
            Write-Host "AtLogon also failed: $_"
        }
    }
}

if (-not $registered) {
    Write-Host "Fallback to schtasks.exe with short path..."
    try {
        $fso = New-Object -ComObject Scripting.FileSystemObject
        $shortPath = if (Test-Path $LauncherVbs) { $fso.GetFile($LauncherVbs).ShortPath } else { $LauncherVbs }
        & schtasks.exe /Create /TN $TaskName /TR "wscript.exe $shortPath" /SC ONSTART /RU "SYSTEM" /RL HIGHEST /F 2>$null
        if ($LASTEXITCODE -ne 0) {
            & schtasks.exe /Create /TN $TaskName /TR "wscript.exe $shortPath" /SC ONLOGON /RL HIGHEST /F
        }
    } catch {
        Write-Host "schtasks fallback error: $_"
    }
}
