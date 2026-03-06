from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from acidnet.eval.persona_reward import reward_breakdown_to_dict, score_dialogue_response


@dataclass(slots=True)
class PreferenceExample:
    custom_id: str
    npc_id: str
    scenario_id: str | None
    prompt: str
    chosen: str
    rejected: str
    messages: list[dict[str, str]]
    chosen_reward: dict[str, object]
    rejected_reward: dict[str, object]


def build_bootstrap_rejected_outputs(prompt_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for prompt_row in prompt_rows:
        if prompt_row.get("task") != "dialogue":
            continue
        sample = extract_world_sample(prompt_row["user_prompt"])
        npc = sample["npc"]
        response = _generic_rejected_response(sample)
        rows.append(
            {
                "custom_id": prompt_row["custom_id"],
                "assistant_json": {
                    "task": "dialogue",
                    "npc_id": npc["npc_id"],
                    "response": response,
                },
                "metadata": {
                    "teacher_type": "bootstrap_rejected",
                    "npc_id": npc["npc_id"],
                    "scenario_id": prompt_row.get("metadata", {}).get("scenario_id"),
                },
            }
        )
    return rows


def build_dialogue_preference_examples(
    prompt_rows: list[dict[str, Any]],
    chosen_rows: list[dict[str, Any]],
    rejected_rows: list[dict[str, Any]],
) -> list[PreferenceExample]:
    chosen_by_id = {row["custom_id"]: _extract_dialogue_text(row) for row in chosen_rows}
    rejected_by_id = {row["custom_id"]: _extract_dialogue_text(row) for row in rejected_rows}

    examples: list[PreferenceExample] = []
    for prompt_row in prompt_rows:
        if prompt_row.get("task") != "dialogue":
            continue
        custom_id = prompt_row["custom_id"]
        chosen = chosen_by_id.get(custom_id)
        rejected = rejected_by_id.get(custom_id)
        if not chosen or not rejected or chosen == rejected:
            continue

        sample = extract_world_sample(prompt_row["user_prompt"])
        chosen_reward = score_dialogue_response(sample, chosen)
        rejected_reward = score_dialogue_response(sample, rejected)
        if chosen_reward.total_score <= rejected_reward.total_score:
            continue

        metadata = prompt_row.get("metadata", {})
        messages = [
            {"role": "system", "content": prompt_row["system_prompt"]},
            {"role": "user", "content": prompt_row["user_prompt"]},
        ]
        examples.append(
            PreferenceExample(
                custom_id=custom_id,
                npc_id=str(metadata.get("npc_id", "")),
                scenario_id=metadata.get("scenario_id"),
                prompt=_render_prompt(messages),
                chosen=chosen,
                rejected=rejected,
                messages=messages,
                chosen_reward=reward_breakdown_to_dict(chosen_reward),
                rejected_reward=reward_breakdown_to_dict(rejected_reward),
            )
        )
    return examples


def export_preference_jsonl(path: str | Path, examples: list[PreferenceExample]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(asdict(example), ensure_ascii=False) + "\n")
    return output_path


def export_preference_parquet(path: str | Path, examples: list[PreferenceExample]) -> Path:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError(
            "Parquet export requires pyarrow. Install it with `python -m pip install -e .[training]`."
        ) from exc

    records = []
    for example in examples:
        record = asdict(example)
        record["messages"] = json.dumps(record["messages"], ensure_ascii=False)
        record["chosen_reward"] = json.dumps(record["chosen_reward"], ensure_ascii=False)
        record["rejected_reward"] = json.dumps(record["rejected_reward"], ensure_ascii=False)
        records.append(record)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(records), output_path)
    return output_path


def extract_world_sample(user_prompt: str) -> dict[str, Any]:
    marker = "World sample:"
    _, sample_text = user_prompt.split(marker, 1)
    return ast.literal_eval(sample_text.strip())


def _extract_dialogue_text(row: dict[str, Any]) -> str | None:
    payload = None
    if "assistant_json" in row and isinstance(row["assistant_json"], dict):
        payload = row["assistant_json"]
    elif "output_json" in row and isinstance(row["output_json"], dict):
        payload = row["output_json"]
    else:
        for key in ("response_text", "output_text", "assistant_text", "response"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                try:
                    payload = json.loads(value)
                except json.JSONDecodeError:
                    payload = {"response": value}
                break
    if not isinstance(payload, dict):
        return None
    response = payload.get("response")
    return str(response).strip() if isinstance(response, str) and response.strip() else None


def _render_prompt(messages: list[dict[str, str]]) -> str:
    return "\n".join(f"{message['role']}: {message['content']}" for message in messages)


def _generic_rejected_response(sample: dict[str, Any]) -> str:
    npc = sample["npc"]
    location = sample["location"]["name"]
    profession = npc["profession"]
    if profession == "guard":
        return "Things are normal enough. Stay out of trouble."
    if profession == "merchant":
        return "Maybe later. The market is the market."
    if profession == "farmer":
        return f"The field near {location} is still there. Hard to say more."
    return f"{npc['name']} shrugs. Things around {location} seem ordinary enough."
