param(
    [ValidateSet("setup", "smoke", "full")]
    [string]$Mode = "smoke",
    [string]$Distro = "Debian",
    [string]$PythonVersion = "3.12",
    [string]$EnvDir = "",
    [string]$RunSuffix = "",
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

function Convert-ToBashLiteral {
    param([AllowEmptyString()][string]$Value)
    return "'" + $Value.Replace("'", "'\''") + "'"
}

$repoRoot = Convert-ToWslPath -WindowsPath "."
$scriptMap = @{
    setup = "scripts/setup_wsl_uv_unsloth.sh"
    smoke = "scripts/launch_qwen3_5_4b_runtime_dialogue_unsloth_wsl_smoke.sh"
    full  = "scripts/launch_qwen3_5_4b_runtime_dialogue_unsloth_wsl_full.sh"
}
$targetScript = $scriptMap[$Mode]
$pythonTag = $PythonVersion.Replace(".", "")
if (-not $EnvDir) {
    $EnvDir = if ($PythonVersion -eq "3.12") { ".venv-wsl" } else { ".venv-wsl-py$pythonTag" }
}
if (-not $RunSuffix) {
    $RunSuffix = if ($PythonVersion -eq "3.12") { "" } else { "_py$pythonTag" }
}
$envExports = @(
    "export ACIDNET_WSL_PYTHON_VERSION=$(Convert-ToBashLiteral $PythonVersion)",
    "export ACIDNET_WSL_ENV_DIR=$(Convert-ToBashLiteral $EnvDir)",
    "export ACIDNET_WSL_RUN_SUFFIX=$(Convert-ToBashLiteral $RunSuffix)"
) -join " && "
$bashCommand = "cd '$repoRoot' && $envExports && bash '$targetScript'"

Write-Output ("WSL mode={0} python={1} env={2} suffix={3}" -f $Mode, $PythonVersion, $EnvDir, $RunSuffix)

if ($Detached) {
    Start-Process -FilePath "wsl.exe" -ArgumentList @("-d", $Distro, "bash", "-lc", $bashCommand) | Out-Null
    Write-Output "Launched WSL $Mode command in detached mode."
    exit 0
}

wsl.exe -d $Distro bash -lc $bashCommand
