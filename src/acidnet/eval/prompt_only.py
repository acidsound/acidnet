from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from acidnet.simulator import Simulation

STOPWORDS = {"the", "and", "with", "this", "that", "have", "from", "will", "into", "your", "about"}
FOOD_TOKENS = {"bread", "fish", "stew", "wheat"}
EXPECTED_ADAPTER_NAMES = {
    "heuristic": "rule_based",
    "openai_compat": "openai_compat",
    "local_peft": "local_peft",
}


@dataclass(slots=True)
class PromptOnlyEvalRow:
    npc_id: str
    npc_name: str
    interaction_mode: str
    interaction_case: str
    player_prompt: str
    response_text: str
    backend: str
    adapter_name: str
    latency_ms: float
    score: float
    passed_checks: list[str]
    failed_checks: list[str]


def run_prompt_only_baseline_eval(
    *,
    dialogue_backend: str = "heuristic",
    dialogue_model: str | None = None,
    dialogue_endpoint: str | None = None,
    dialogue_adapter_path: str | None = None,
) -> list[PromptOnlyEvalRow]:
    simulation = Simulation.create_demo(
        dialogue_backend=dialogue_backend,
        dialogue_model=dialogue_model,
        dialogue_endpoint=dialogue_endpoint,
        dialogue_adapter_path=dialogue_adapter_path,
    )
    if hasattr(simulation.dialogue_adapter, "temperature"):
        simulation.dialogue_adapter.temperature = 0.0
    rows: list[PromptOnlyEvalRow] = []

    for npc_id, npc in simulation.npcs.items():
        cases = [
            ("talk", "scene_talk", "What is going on around here?"),
            ("direct_say", "origin_direct", "Where did you come from?"),
            ("direct_say", "identity_direct", "I do not think we have met. Who are you?"),
            ("direct_say", "hunger_direct", "I am hungry."),
        ]
        if npc.is_vendor:
            cases.append(("trade_request", "trade_request_stock", "I need food. What can you sell me right now?"))
        if npc.known_rumor_ids:
            cases.append(("rumor_request", "rumor_request_known", "Have you heard any useful rumors?"))

        for interaction_mode, interaction_case, player_prompt in cases:
            result = simulation.probe_npc_dialogue_result(
                npc_id,
                interaction_mode=interaction_mode,
                player_prompt=player_prompt,
            )
            response = result.text
            passed, failed = _evaluate_response(
                simulation,
                npc_id,
                interaction_mode,
                interaction_case,
                player_prompt,
                response,
            )
            total = len(passed) + len(failed)
            score = len(passed) / total if total else 0.0
            rows.append(
                PromptOnlyEvalRow(
                    npc_id=npc_id,
                    npc_name=npc.name,
                    interaction_mode=interaction_mode,
                    interaction_case=interaction_case,
                    player_prompt=player_prompt,
                    response_text=response,
                    backend=dialogue_backend,
                    adapter_name=result.adapter_name,
                    latency_ms=round(result.latency_ms, 3),
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
    average_latency = sum(row.latency_ms for row in rows) / max(1, len(rows))
    fallback_rows = count_backend_fallback_rows(rows)
    return (
        f"rows={len(rows)} average_score={average:.3f} rows_with_failures={failed} "
        f"average_latency_ms={average_latency:.1f} fallback_rows={fallback_rows}"
    )


def expected_adapter_name_for_backend(backend: str) -> str:
    return EXPECTED_ADAPTER_NAMES.get(backend, backend)


def count_backend_fallback_rows(rows: list[PromptOnlyEvalRow]) -> int:
    return sum(1 for row in rows if row.adapter_name != expected_adapter_name_for_backend(row.backend))


def _evaluate_response(
    simulation: Simulation,
    npc_id: str,
    interaction_mode: str,
    interaction_case: str,
    player_prompt: str,
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
        overlaps = []
        for rumor_id in npc.known_rumor_ids:
            rumor = simulation.rumors.get(rumor_id)
            if rumor is None:
                continue
            tokens = _meaningful_tokens(rumor.content)
            overlaps.append(sum(1 for token in tokens if token in normalized))
        _check(max(overlaps, default=0) >= 2, "mentions_known_rumor", passed, failed)

    if interaction_mode == "trade_request" and npc.is_vendor:
        stocked_items = [item for item, qty in npc.inventory.items() if qty > 0]
        edible_stocked_items = [item for item, qty in npc.inventory.items() if qty > 0 and item in FOOD_TOKENS]
        asks_for_food = any(token in player_prompt.lower() for token in ("food", "hungry", "eat", "meal"))
        claimed_food_items = [item for item in FOOD_TOKENS if item in normalized]
        invented_food_stock = any(
            item not in edible_stocked_items
            and any(
                phrase in normalized
                for phrase in (
                    f"have {item}",
                    f"{item} on hand",
                    f"spare {item}",
                    f"sell {item}",
                    f"{item} nearby",
                )
            )
            for item in claimed_food_items
        )
        if asks_for_food and edible_stocked_items:
            _check(any(item in normalized for item in edible_stocked_items), "mentions_stocked_food_item", passed, failed)
        elif asks_for_food:
            shortage_words = {"no food", "do not have food", "bakery", "tavern", "shrine", "nothing edible", "try the"}
            _check(any(word in normalized for word in shortage_words), "answers_food_trade_without_fake_stock", passed, failed)
            _check(not invented_food_stock, "does_not_invent_food_stock", passed, failed)
        else:
            _check(any(item in normalized for item in stocked_items), "mentions_stocked_item", passed, failed)

    if interaction_mode == "direct_say":
        if interaction_case == "origin_direct":
            location_tokens = _meaningful_tokens(simulation.world.locations[npc.location_id].name)
            answered_origin = (
                any(token in normalized for token in location_tokens)
                or "from" in normalized
                or "stay" in normalized
                or "keep close" in normalized
                or "nothing farther" in normalized
            )
            _check(answered_origin, "answers_direct_origin_question", passed, failed)
        elif interaction_case == "identity_direct":
            profession_token = npc.profession.lower()
            answered_identity = (
                npc.name.lower() in normalized
                or profession_token in normalized
                or "call me" in normalized
                or "i am " in normalized
                or "i'm " in normalized
            )
            _check(answered_identity, "answers_identity_question", passed, failed)
        elif interaction_case == "hunger_direct":
            stocked_items = [item for item, qty in npc.inventory.items() if qty > 0 and item in FOOD_TOKENS]
            food_words = {"bread", "fish", "stew", "wheat", "food", "eat", "meal", "bakery", "shrine", "square", "hungry"}
            support_words = {"have", "take", "try", "come", "sell", "spare", "share", "help"}
            claimed_food_items = [item for item in FOOD_TOKENS if item in normalized]
            invented_food_stock = any(
                item not in stocked_items
                and any(
                    phrase in normalized
                    for phrase in (
                        f"have {item}",
                        f"{item} on hand",
                        f"spare {item}",
                        f"sell {item}",
                        f"{item} nearby",
                    )
                )
                for item in claimed_food_items
            )
            answered_hunger = (
                any(item in normalized for item in stocked_items)
                or any(word in normalized for word in food_words)
            ) and any(word in normalized for word in support_words)
            _check(answered_hunger, "answers_hunger_request", passed, failed)
            _check(not invented_food_stock, "does_not_invent_food_stock", passed, failed)

    return passed, failed


def _meaningful_tokens(text: str) -> list[str]:
    tokens = [token for token in re.findall(r"[a-zA-Z_]+", text.lower()) if len(token) >= 4 and token not in STOPWORDS]
    return tokens[:6]


def _check(condition: bool, label: str, passed: list[str], failed: list[str]) -> None:
    if condition:
        passed.append(label)
    else:
        failed.append(label)
