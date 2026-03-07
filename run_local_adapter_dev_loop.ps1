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
    [switch]$TailLog,
    [string]$WebHost = "127.0.0.1",
    [int]$WebPort = 8765,
    [string]$WebEventLogPath = "data/logs/local-adapter-web.log"
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

$WebArgs = @(
    "run_acidnet_web.py",
    "--host", $WebHost,
    "--port", $WebPort,
    "--dialogue-backend", "openai_compat",
    "--dialogue-model", $ModelAlias,
    "--dialogue-endpoint", $Endpoint,
    "--event-log", $WebEventLogPath
)
if (-not $Persist) {
    $WebArgs += "--no-persist"
}
if ($TailLog -and $WebEventLogPath) {
    Start-Process -FilePath "powershell" `
        -ArgumentList @("-ExecutionPolicy", "Bypass", "-File", ".\run_tail_event_log.ps1", "-Path", $WebEventLogPath) `
        -WorkingDirectory $ScriptRoot | Out-Null
}

$WebProcess = Start-Process -FilePath python -ArgumentList $WebArgs -WorkingDirectory $ScriptRoot -PassThru
Write-Host ("Started acidnet web runtime (PID {0}) at http://{1}:{2}" -f $WebProcess.Id, $WebHost, $WebPort)
if (-not $Persist) {
    Write-Host "Persistence disabled for this observation session."
}
Write-Host ("Web event log: {0}" -f $WebEventLogPath)
