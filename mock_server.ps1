# Mock HTTPS Server Launcher per PowerShell
$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$ServerScript = Join-Path $PSScriptRoot "mock_server.py"
& $VenvPython $ServerScript @args
