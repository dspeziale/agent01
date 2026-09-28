$LauncherVbs = "C:\Program Files\Sysmon\sysmon_service.vbs"
$TaskName = "SysmonAgentTest"

Write-Host "--- Test A: Register-ScheduledTask ---"
if (Get-Command Register-ScheduledTask -ErrorAction SilentlyContinue) {
    Write-Host "Register-ScheduledTask cmdlet is available!"
    $action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$LauncherVbs`""
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings
    Write-Host "Task object created successfully."
}

Write-Host "`n--- Test B: cmd /c with proper nested quotes ---"
# In cmd.exe, the entire string passed to /c must be wrapped in an extra set of outer quotes:
# cmd.exe /c "schtasks.exe /Create /TN ... /TR "\"wscript.exe\" \"C:\Program Files\...\"" ..."
$cmd = 'schtasks.exe /Create /TN ' + $TaskName + ' /TR "\"wscript.exe\" \"' + $LauncherVbs + '\"" /SC ONSTART /RU SYSTEM /RL HIGHEST /F'
Write-Host "Cmd string: $cmd"
$res = cmd.exe /c "`"$cmd`"" 2>&1
Write-Host "Cmd output: $res"
