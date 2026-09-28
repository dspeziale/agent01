# Pulsar Launcher per Windows PowerShell
$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$MainScript = Join-Path $PSScriptRoot "main.py"
& $VenvPython $MainScript @args
