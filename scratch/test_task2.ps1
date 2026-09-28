$LauncherVbs = "C:\Program Files\Sysmon\sysmon_service.vbs"
$TaskName = "SysmonAgent"

# Method: schtasks command line with perfect quote escaping
# In cmd.exe syntax for schtasks /TR:
# To pass: wscript.exe "C:\Program Files\Sysmon\sysmon_service.vbs"
# /TR requires escaped quotes: "\"wscript.exe\" \"C:\Program Files\Sysmon\sysmon_service.vbs\""
$escapedTr = "\`"wscript.exe\`" \`"$LauncherVbs\`""

Write-Host "Escaped TR: $escapedTr"

# Test invoking schtasks directly from PowerShell without cmd.exe /c:
# When invoking directly:
# & schtasks.exe /Create /TN $TaskName /TR "\"wscript.exe\" \"$LauncherVbs\"" /SC ONSTART /RU "SYSTEM" /RL HIGHEST /F
try {
    $out = & schtasks.exe /Create /TN $TaskName /TR "\"wscript.exe\" \"$LauncherVbs\"" /SC ONSTART /RU "SYSTEM" /RL HIGHEST /F 2>&1
    Write-Host "Output: $out"
} catch {
    Write-Host "Error: $_"
}
