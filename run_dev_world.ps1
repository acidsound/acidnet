param(
    [ValidateSet("heuristic", "openai_compat")]
    [string]$DialogueBackend = "heuristic",
    [string]$DialogueModel = "",
    [string]$DialogueEndpoint = "",
    [switch]$Persist,
    [switch]$RunPromptOnlyEval,
    [switch]$Detached,
    [switch]$NoMonkey,
    [int]$MonkeySteps = 160,
    [int]$MonkeyDelayMs = 350,
    [int]$MonkeySeed = 7
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptRoot

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
    Write-Host "Running prompt-only baseline eval..."
    & python @EvalArgs
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
    exit 0
}

Write-Host ("Launching acidnet GUI with backend '{0}'..." -f $DialogueBackend)
if (-not $Persist) {
    Write-Host "Persistence disabled for this observation session."
}
if (-not $NoMonkey) {
    Write-Host ("Monkey mode enabled: {0} steps, {1}ms delay, seed {2}." -f $MonkeySteps, $MonkeyDelayMs, $MonkeySeed)
}
& python @GuiArgs
