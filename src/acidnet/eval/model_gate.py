from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from acidnet.eval.circulation import CirculationReport, run_circulation_eval
from acidnet.eval.prompt_only import PromptOnlyEvalRow, run_prompt_only_baseline_eval
from acidnet.engine import Simulation


@dataclass(slots=True)
class ModelGateReport:
    backend: str
    model: str | None
    endpoint: str | None
    prompt_average_score: float
    prompt_average_latency_ms: float
    prompt_max_latency_ms: float
    prompt_rows: int
    prompt_rows_with_failures: int
    prompt_fallback_rows: int
    prompt_adapter_names: list[str]
    prompt_failures: list[str]
    circulation: CirculationReport
    gate_passed: bool
    gate_failures: list[str]


def run_model_gate(
    *,
    dialogue_backend: str,
    dialogue_model: str | None = None,
    dialogue_endpoint: str | None = None,
    dialogue_adapter_path: str | None = None,
    circulation_turns: int = 120,
) -> ModelGateReport:
    prompt_rows = run_prompt_only_baseline_eval(
        dialogue_backend=dialogue_backend,
        dialogue_model=dialogue_model,
        dialogue_endpoint=dialogue_endpoint,
        dialogue_adapter_path=dialogue_adapter_path,
    )
    prompt_average_score = sum(row.score for row in prompt_rows) / max(1, len(prompt_rows))
    prompt_average_latency_ms = sum(row.latency_ms for row in prompt_rows) / max(1, len(prompt_rows))
    prompt_max_latency_ms = max((row.latency_ms for row in prompt_rows), default=0.0)
    prompt_rows_with_failures = sum(1 for row in prompt_rows if row.failed_checks)
    prompt_fallback_rows = sum(1 for row in prompt_rows if row.backend == "openai_compat" and row.adapter_name != "openai_compat")
    prompt_adapter_names = sorted({row.adapter_name for row in prompt_rows})
    prompt_failures = sorted(
        {
            f"{row.npc_name}:{row.interaction_mode}:{failure}"
            for row in prompt_rows
            for failure in row.failed_checks
        }
    )

    circulation_report = run_circulation_eval(
        Simulation.create_demo(
            dialogue_backend=dialogue_backend,
            dialogue_model=dialogue_model,
            dialogue_endpoint=dialogue_endpoint,
            dialogue_adapter_path=dialogue_adapter_path,
        ),
        turns=circulation_turns,
    )

    gate_failures: list[str] = []
    if prompt_average_score < 0.85:
        gate_failures.append("prompt_average_score_below_threshold")
    if prompt_rows_with_failures > 2:
        gate_failures.append("too_many_prompt_failures")
    if dialogue_backend == "openai_compat" and prompt_fallback_rows > 2:
        gate_failures.append("too_many_prompt_fallbacks")
    if dialogue_backend == "openai_compat" and prompt_average_latency_ms > 4000.0:
        gate_failures.append("prompt_latency_too_high")
    if circulation_report.average_active_locations < 4.0:
        gate_failures.append("low_spatial_activity")
    if circulation_report.starving_npc_count > 1:
        gate_failures.append("npc_starvation")
    if "hard_clustering" in circulation_report.flags:
        gate_failures.append("hard_clustering")

    return ModelGateReport(
        backend=dialogue_backend,
        model=dialogue_model,
        endpoint=dialogue_endpoint,
        prompt_average_score=round(prompt_average_score, 3),
        prompt_average_latency_ms=round(prompt_average_latency_ms, 3),
        prompt_max_latency_ms=round(prompt_max_latency_ms, 3),
        prompt_rows=len(prompt_rows),
        prompt_rows_with_failures=prompt_rows_with_failures,
        prompt_fallback_rows=prompt_fallback_rows,
        prompt_adapter_names=prompt_adapter_names,
        prompt_failures=prompt_failures,
        circulation=circulation_report,
        gate_passed=not gate_failures,
        gate_failures=gate_failures,
    )


def export_model_gate_json(path: str | Path, report: ModelGateReport) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def summarize_model_gate(report: ModelGateReport) -> str:
    outcome = "PASS" if report.gate_passed else "FAIL"
    return (
        f"{outcome} backend={report.backend} model={report.model or '-'} "
        f"prompt_avg={report.prompt_average_score:.3f} "
        f"prompt_fail_rows={report.prompt_rows_with_failures} "
        f"prompt_latency_ms={report.prompt_average_latency_ms:.1f} "
        f"prompt_fallbacks={report.prompt_fallback_rows} "
        f"circulation={report.circulation.circulation_score:.3f} "
        f"starving={report.circulation.starving_npc_count}"
    )
