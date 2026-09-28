<#
.SYNOPSIS
    Root wrapper for scripts/install-windows.ps1
#>
param(
    [string]$ServerUrl = "https://simei.dsc-italy.app/api/v1/metrics",
    [string]$Token = "",
    [int]$Interval = 15,
    [string]$InstallDir = "",
    [switch]$Status,
    [switch]$Uninstall
)

$targetScript = Join-Path $PSScriptRoot "scripts\install-windows.ps1"
if (-not (Test-Path $targetScript)) {
    throw "Impossibile trovare $targetScript"
}

& $targetScript @PSBoundParameters
