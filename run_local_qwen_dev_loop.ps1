param(
    [Parameter(Mandatory = $true)]
    [string]$ModelPath,
    [string]$ServerPath = "llama-server",
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000,
    [int]$ContextSize = 4096,
    [int]$GpuLayers = 99,
    [string]$ModelAlias = "qwen3.5-4b",
    [int]$StartupTimeoutSeconds = 45,
    [int]$ModelGateTurns = 120,
    [switch]$Persist,
    [switch]$NoMonkey,
    [switch]$TailLog
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptRoot

$ResolvedModelPath = Resolve-Path $ModelPath
$Endpoint = "http://{0}:{1}/v1/chat/completions" -f $Host, $Port
$ModelsEndpoint = "http://{0}:{1}/v1/models" -f $Host, $Port

Write-Host ("Starting local Qwen dev loop with model '{0}'..." -f $ResolvedModelPath)

$ServerProcess = Start-Process -FilePath $ServerPath -ArgumentList @(
    "-m", $ResolvedModelPath,
    "--host", $Host,
    "--port", $Port,
    "-c", $ContextSize,
    "-ngl", $GpuLayers,
    "--alias", $ModelAlias
) -WorkingDirectory $ScriptRoot -PassThru

Write-Host ("llama-server PID: {0}" -f $ServerProcess.Id)
Write-Host ("Waiting for endpoint: {0}" -f $ModelsEndpoint)

$Deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
$Ready = $false
while ((Get-Date) -lt $Deadline) {
    try {
        Invoke-WebRequest -Uri $ModelsEndpoint -UseBasicParsing -TimeoutSec 5 | Out-Null
        $Ready = $true
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $Ready) {
    throw ("Timed out waiting for local model server at {0}" -f $ModelsEndpoint)
}

Write-Host "Running combined model gate..."
& python run_model_gate.py `
    --dialogue-backend openai_compat `
    --dialogue-model $ModelAlias `
    --dialogue-endpoint $Endpoint `
    --turns $ModelGateTurns `
    --output data/eval/local_qwen_model_gate_report.json

$GuiArgs = @(
    "-ExecutionPolicy", "Bypass",
    "-File", ".\run_dev_world.ps1",
    "-DialogueBackend", "openai_compat",
    "-DialogueModel", $ModelAlias,
    "-DialogueEndpoint", $Endpoint,
    "-RunModelGate",
    "-ModelGateTurns", $ModelGateTurns,
    "-Detached"
)
if ($Persist) {
    $GuiArgs += "-Persist"
}
if ($NoMonkey) {
    $GuiArgs += "-NoMonkey"
}
if ($TailLog) {
    $GuiArgs += "-TailLog"
}

Write-Host "Launching GUI against local model backend..."
& powershell @GuiArgs
