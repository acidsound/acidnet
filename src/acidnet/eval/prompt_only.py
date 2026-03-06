from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from acidnet.engine import Simulation

STOPWORDS = {"the", "and", "with", "this", "that", "have", "from", "will", "into", "your", "about"}


@dataclass(slots=True)
class PromptOnlyEvalRow:
    npc_id: str
    npc_name: str
    interaction_mode: str
    player_prompt: str
    response_text: str
    backend: str
    score: float
    passed_checks: list[str]
    failed_checks: list[str]


def run_prompt_only_baseline_eval(
    *,
    dialogue_backend: str = "heuristic",
    dialogue_model: str | None = None,
    dialogue_endpoint: str | None = None,
) -> list[PromptOnlyEvalRow]:
    simulation = Simulation.create_demo(
        dialogue_backend=dialogue_backend,
        dialogue_model=dialogue_model,
        dialogue_endpoint=dialogue_endpoint,
    )
    rows: list[PromptOnlyEvalRow] = []

    for npc_id, npc in simulation.npcs.items():
        cases = [("talk", "What is going on around here?")]
        if npc.is_vendor:
            cases.append(("trade_request", "I need food. What can you sell me right now?"))
        if npc.known_rumor_ids:
            cases.append(("rumor_request", "Have you heard any useful rumors?"))

        for interaction_mode, player_prompt in cases:
            response = simulation.probe_npc_dialogue(
                npc_id,
                interaction_mode=interaction_mode,
                player_prompt=player_prompt,
            )
            passed, failed = _evaluate_response(simulation, npc_id, interaction_mode, response)
            total = len(passed) + len(failed)
            score = len(passed) / total if total else 0.0
            rows.append(
                PromptOnlyEvalRow(
                    npc_id=npc_id,
                    npc_name=npc.name,
                    interaction_mode=interaction_mode,
                    player_prompt=player_prompt,
                    response_text=response,
                    backend=dialogue_backend,
                    score=round(score, 3),
                    passed_checks=passed,
                    failed_checks=failed,
                )
            )
    return rows


def export_prompt_only_eval_json(path: str | Path, rows: list[PromptOnlyEvalRow]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps([asdict(row) for row in rows], ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def summarize_scores(rows: list[PromptOnlyEvalRow]) -> str:
    average = sum(row.score for row in rows) / max(1, len(rows))
    failed = sum(1 for row in rows if row.failed_checks)
    return f"rows={len(rows)} average_score={average:.3f} rows_with_failures={failed}"


def _evaluate_response(
    simulation: Simulation,
    npc_id: str,
    interaction_mode: str,
    response: str,
) -> tuple[list[str], list[str]]:
    passed: list[str] = []
    failed: list[str] = []

    normalized = response.lower()
    npc = simulation.npcs[npc_id]

    _check(bool(response.strip()), "non_empty", passed, failed)
    _check(12 <= len(response.strip()) <= 280, "reasonable_length", passed, failed)
    _check("as an ai" not in normalized and "language model" not in normalized and "assistant" not in normalized, "no_meta_leak", passed, failed)

    if interaction_mode == "rumor_request" and npc.known_rumor_ids:
        rumor = simulation.rumors[npc.known_rumor_ids[0]]
        tokens = _meaningful_tokens(rumor.content)
        overlap = sum(1 for token in tokens if token in normalized)
        _check(overlap >= 2, "mentions_known_rumor", passed, failed)

    if interaction_mode == "trade_request" and npc.is_vendor:
        stocked_items = [item for item, qty in npc.inventory.items() if qty > 0]
        _check(any(item in normalized for item in stocked_items), "mentions_stocked_item", passed, failed)

    return passed, failed


def _meaningful_tokens(text: str) -> list[str]:
    tokens = [token for token in re.findall(r"[a-zA-Z_]+", text.lower()) if len(token) >= 4 and token not in STOPWORDS]
    return tokens[:6]


def _check(condition: bool, label: str, passed: list[str], failed: list[str]) -> None:
    if condition:
        passed.append(label)
    else:
        failed.append(label)
