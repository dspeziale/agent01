$LauncherVbs = "C:\Program Files\Sysmon\sysmon_service.vbs"
$TaskName = "SysmonAgentTest"

# Test 1: Native PowerShell ScheduledTask cmdlets (Available in Windows PowerShell 5.1 and PS7+)
Write-Host "--- Test 1: ScheduledTask Cmdlet ---"
try {
    $action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$LauncherVbs`""
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    $task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings
    Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force
    Write-Host "Register-ScheduledTask SUCCESS!" -ForegroundColor Green
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
} catch {
    Write-Host "Register-ScheduledTask Error: $_" -ForegroundColor Red
}

# Test 2: schtasks.exe syntax
Write-Host "`n--- Test 2: schtasks syntax ---"
# Notice that for schtasks /TR: the entire argument must be passed with escaped inner quotes:
# /TR "\"wscript.exe\" \"C:\Program Files\Sysmon\sysmon_service.vbs\""
$taskRun = "\`"wscript.exe\`" \`"$LauncherVbs\`""
Write-Host "TaskRun string: $taskRun"
cmd.exe /c "schtasks.exe /Create /TN $TaskName /TR ""\""wscript.exe\"" \""$LauncherVbs\"""" /SC ONSTART /RU SYSTEM /RL HIGHEST /F"
Write-Host "Exit code: $LASTEXITCODE"
if ($LASTEXITCODE -eq 0) {
    schtasks.exe /Delete /TN $TaskName /F
}
