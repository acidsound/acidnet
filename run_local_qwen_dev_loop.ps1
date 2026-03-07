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
    [string]$ModelAlias = "qwen3.5-4b",
    [int]$StartupTimeoutSeconds = 45,
    [int]$ModelGateTurns = 120,
    [switch]$Persist,
    [switch]$TailLog,
    [string]$WebHost = "127.0.0.1",
    [int]$WebPort = 8765,
    [string]$WebEventLogPath = "data/logs/local-qwen-web.log"
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptRoot

$ResolvedModelPath = Resolve-Path $ModelPath
$Endpoint = "http://{0}:{1}/v1/chat/completions" -f $Host, $Port
$ModelsEndpoint = "http://{0}:{1}/v1/models" -f $Host, $Port

Write-Host ("Starting local Qwen dev loop with model '{0}'..." -f $ResolvedModelPath)

$ServerArgs = @(
    "-m", $ResolvedModelPath,
    "--host", $Host,
    "--port", $Port,
    "-c", $ContextSize,
    "-ngl", $GpuLayers,
    "--alias", $ModelAlias
)
if ($LoraPath) {
    $ResolvedLoraPath = Resolve-Path $LoraPath
    if ($LoraScale -eq 1.0) {
        $ServerArgs += @("--lora", $ResolvedLoraPath)
    } else {
        $ServerArgs += @("--lora-scaled", $ResolvedLoraPath, $LoraScale)
    }
}

$ServerProcess = Start-Process -FilePath $ServerPath -ArgumentList $ServerArgs -WorkingDirectory $ScriptRoot -PassThru

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
