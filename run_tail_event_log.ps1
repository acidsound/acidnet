param(
    [string]$Path = "data/logs/dev-world.log",
    [int]$Last = 30
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptRoot

if (-not (Test-Path $Path)) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null
    New-Item -ItemType File -Force -Path $Path | Out-Null
}

Write-Host ("Tailing event log: {0}" -f $Path)
Get-Content -Path $Path -Tail $Last -Wait
