param(
    [Parameter(Mandatory = $true)]
    [string]$ModelPath,
    [string]$LoraPath = "",
    [double]$LoraScale = 1.0,
    [string]$ServerPath = "llama-server",
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000,
    [int]$ContextSize = 4096,
    [int]$GpuLayers = 99,
    [string]$Alias = "qwen3.5-4b",
    [switch]$Detached
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptRoot

$ResolvedModelPath = Resolve-Path $ModelPath
$Args = @(
    "-m", $ResolvedModelPath,
    "--host", $Host,
    "--port", $Port,
    "-c", $ContextSize,
    "-ngl", $GpuLayers,
    "--alias", $Alias
)
if ($LoraPath) {
    $ResolvedLoraPath = Resolve-Path $LoraPath
    if ($LoraScale -eq 1.0) {
        $Args += @("--lora", $ResolvedLoraPath)
    } else {
        $Args += @("--lora-scaled", $ResolvedLoraPath, $LoraScale)
    }
}

Write-Host ("Launching llama-server with model '{0}'..." -f $ResolvedModelPath)
Write-Host ("Endpoint: http://{0}:{1}/v1/chat/completions" -f $Host, $Port)

if ($Detached) {
    $Process = Start-Process -FilePath $ServerPath -ArgumentList $Args -WorkingDirectory $ScriptRoot -PassThru
    Write-Host ("Started llama-server (PID {0})." -f $Process.Id)
    exit 0
}

& $ServerPath @Args
