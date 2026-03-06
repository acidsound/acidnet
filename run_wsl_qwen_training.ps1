param(
    [ValidateSet("setup", "smoke", "full")]
    [string]$Mode = "smoke",
    [string]$Distro = "Debian",
    [switch]$Detached
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Convert-ToWslPath {
    param([Parameter(Mandatory = $true)][string]$WindowsPath)
    $resolved = (Resolve-Path $WindowsPath).Path
    $drive = $resolved.Substring(0, 1).ToLowerInvariant()
    $rest = $resolved.Substring(2).Replace("\", "/")
    return "/mnt/$drive$rest"
}

$repoRoot = Convert-ToWslPath -WindowsPath "."
$scriptMap = @{
    setup = "scripts/setup_wsl_uv_unsloth.sh"
    smoke = "scripts/launch_qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke.sh"
    full  = "scripts/launch_qwen3_5_4b_runtime_dialogue_unsloth_wsl_full.sh"
}
$targetScript = $scriptMap[$Mode]
$bashCommand = "cd '$repoRoot' && bash '$targetScript'"

if ($Detached) {
    Start-Process -FilePath "wsl.exe" -ArgumentList @("-d", $Distro, "bash", "-lc", $bashCommand) | Out-Null
    Write-Output "Launched WSL $Mode command in detached mode."
    exit 0
}

wsl.exe -d $Distro bash -lc $bashCommand
