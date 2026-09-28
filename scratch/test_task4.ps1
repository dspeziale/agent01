$LauncherVbs = "C:\Program Files\Sysmon\sysmon_service.vbs"
$TaskName = "SysmonAgentTest"

# In PowerShell, calling an external executable like schtasks.exe with an argument array:
# The issue with /TR is that schtasks.exe receives the argument and expects escaped quotes inside it.
# If we write a small XML file or use Register-ScheduledTask:
Write-Host "--- Test 4A: Register-ScheduledTask with Action wscript ---"
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$LauncherVbs`""
Write-Host "Action Execute: $($action.Execute) Argument: $($action.Arguments)"

Write-Host "--- Test 4B: schtasks with short path (8.3 notation) ---"
# Windows short path eliminates spaces completely! E.g. C:\PROGRA~1\Sysmon\sysmon_service.vbs
$fso = New-Object -ComObject Scripting.FileSystemObject
if (Test-Path "C:\Program Files") {
    $shortFolder = $fso.GetFolder("C:\Program Files").ShortPath
    Write-Host "ShortPath for Program Files: $shortFolder"
}
