param(
    [ValidateSet("heuristic", "openai_compat", "local_peft")]
    [string]$DialogueBackend = "heuristic",
    [string]$DialogueModel = "",
    [string]$DialogueEndpoint = "",
    [string]$DialogueAdapterPath = "",
    [switch]$Persist,
    [switch]$RunPromptOnlyEval,
    [switch]$RunModelGate,
    [int]$ModelGateTurns = 120,
    [switch]$Detached,
    [switch]$NoMonkey,
    [int]$MonkeySteps = 160,
    [int]$MonkeyDelayMs = 350,
    [int]$MonkeySeed = 7,
    [string]$EventLogPath = "data/logs/dev-world.log",
    [switch]$NoEventLog,
    [switch]$TailLog
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptRoot

if ($DialogueBackend -eq "local_peft" -and -not $DialogueAdapterPath) {
    throw "DialogueAdapterPath is required when DialogueBackend is 'local_peft'."
}

$GuiArgs = @("run_acidnet_gui.py", "--dialogue-backend", $DialogueBackend)
if (-not $Persist) {
    $GuiArgs += "--no-persist"
}
if ($DialogueModel) {
    $GuiArgs += "--dialogue-model"
    $GuiArgs += $DialogueModel
}
if ($DialogueEndpoint) {
    $GuiArgs += "--dialogue-endpoint"
    $GuiArgs += $DialogueEndpoint
}
if ($DialogueAdapterPath) {
    $GuiArgs += "--dialogue-adapter-path"
    $GuiArgs += $DialogueAdapterPath
}
if ($NoEventLog) {
    $GuiArgs += "--no-event-log"
} else {
    $GuiArgs += "--event-log"
    $GuiArgs += $EventLogPath
}
if (-not $NoMonkey) {
    $GuiArgs += "--monkey"
    $GuiArgs += "--monkey-steps"
    $GuiArgs += $MonkeySteps
    $GuiArgs += "--monkey-delay-ms"
    $GuiArgs += $MonkeyDelayMs
    $GuiArgs += "--monkey-seed"
    $GuiArgs += $MonkeySeed
}

if ($RunPromptOnlyEval) {
    $EvalArgs = @(
        "run_prompt_only_baseline_eval.py",
        "--dialogue-backend", $DialogueBackend,
        "--output", "data/eval/dev_prompt_only_baseline_report.json"
    )
    if ($DialogueModel) {
        $EvalArgs += "--dialogue-model"
        $EvalArgs += $DialogueModel
    }
    if ($DialogueEndpoint) {
        $EvalArgs += "--dialogue-endpoint"
        $EvalArgs += $DialogueEndpoint
    }
    if ($DialogueAdapterPath) {
        $EvalArgs += "--dialogue-adapter-path"
        $EvalArgs += $DialogueAdapterPath
    }
    Write-Host "Running prompt-only baseline eval..."
    & python @EvalArgs
}

if ($RunModelGate) {
    $GateArgs = @(
        "run_model_gate.py",
        "--dialogue-backend", $DialogueBackend,
        "--turns", $ModelGateTurns,
        "--output", "data/eval/dev_model_gate_report.json"
    )
    if ($DialogueModel) {
        $GateArgs += "--dialogue-model"
        $GateArgs += $DialogueModel
    }
    if ($DialogueEndpoint) {
        $GateArgs += "--dialogue-endpoint"
        $GateArgs += $DialogueEndpoint
    }
    if ($DialogueAdapterPath) {
        $GateArgs += "--dialogue-adapter-path"
        $GateArgs += $DialogueAdapterPath
    }
    Write-Host "Running combined model gate..."
    & python @GateArgs
}

if ($TailLog -and -not $NoEventLog) {
    Start-Process -FilePath "powershell" `
        -ArgumentList @("-ExecutionPolicy", "Bypass", "-File", ".\run_tail_event_log.ps1", "-Path", $EventLogPath) `
        -WorkingDirectory $ScriptRoot | Out-Null
}

if ($Detached) {
    $Process = Start-Process -FilePath "python" -ArgumentList $GuiArgs -WorkingDirectory $ScriptRoot -PassThru
    Write-Host ("Started acidnet GUI (PID {0}) with backend '{1}'." -f $Process.Id, $DialogueBackend)
    if (-not $Persist) {
        Write-Host "Persistence disabled for this observation session."
    }
    if (-not $NoMonkey) {
        Write-Host ("Monkey mode enabled: {0} steps, {1}ms delay, seed {2}." -f $MonkeySteps, $MonkeyDelayMs, $MonkeySeed)
    }
    if (-not $NoEventLog) {
        Write-Host ("Event log: {0}" -f $EventLogPath)
    }
    exit 0
}

Write-Host ("Launching acidnet GUI with backend '{0}'..." -f $DialogueBackend)
if (-not $Persist) {
    Write-Host "Persistence disabled for this observation session."
}
if (-not $NoMonkey) {
    Write-Host ("Monkey mode enabled: {0} steps, {1}ms delay, seed {2}." -f $MonkeySteps, $MonkeyDelayMs, $MonkeySeed)
}
if (-not $NoEventLog) {
    Write-Host ("Event log: {0}" -f $EventLogPath)
}
& python @GuiArgs
