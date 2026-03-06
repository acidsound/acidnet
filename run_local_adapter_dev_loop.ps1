param(
    [Parameter(Mandatory = $true)]
    [string]$AdapterPath,
    [string]$BaseModel = "Qwen/Qwen3.5-4B",
    [string]$Host = "127.0.0.1",
    [int]$Port = 8001,
    [string]$ModelAlias = "acidnet-qwen3.5-4b-lora",
    [int]$StartupTimeoutSeconds = 90,
    [int]$ModelGateTurns = 120,
    [switch]$LoadIn4Bit,
    [switch]$Persist,
    [switch]$NoMonkey,
    [switch]$TailLog
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptRoot

$ResolvedAdapterPath = Resolve-Path $AdapterPath
$Endpoint = "http://{0}:{1}/v1/chat/completions" -f $Host, $Port
$ModelsEndpoint = "http://{0}:{1}/v1/models" -f $Host, $Port

$ServerArgs = @(
    "run_local_adapter_server.py",
    "--adapter-path", $ResolvedAdapterPath,
    "--base-model", $BaseModel,
    "--host", $Host,
    "--port", $Port,
    "--model-alias", $ModelAlias
)
if ($LoadIn4Bit) {
    $ServerArgs += "--load-in-4bit"
}

Write-Host ("Starting local adapter server with adapter '{0}'..." -f $ResolvedAdapterPath)
$ServerProcess = Start-Process -FilePath python -ArgumentList $ServerArgs -WorkingDirectory $ScriptRoot -PassThru

Write-Host ("adapter-server PID: {0}" -f $ServerProcess.Id)
Write-Host ("Waiting for endpoint: {0}" -f $ModelsEndpoint)

$Deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
$Ready = $false
while ((Get-Date) -lt $Deadline) {
    try {
        Invoke-WebRequest -Uri $ModelsEndpoint -UseBasicParsing -TimeoutSec 5 | Out-Null
        $Ready = $true
        break
    } catch {
        Start-Sleep -Seconds 3
    }
}

if (-not $Ready) {
    throw ("Timed out waiting for adapter server at {0}" -f $ModelsEndpoint)
}

Write-Host "Running combined model gate..."
& python run_model_gate.py `
    --dialogue-backend openai_compat `
    --dialogue-model $ModelAlias `
    --dialogue-endpoint $Endpoint `
    --turns $ModelGateTurns `
    --output data/eval/local_adapter_model_gate_report.json

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

Write-Host "Launching GUI against local adapter backend..."
& powershell @GuiArgs
