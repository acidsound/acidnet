from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from acidnet.llm.prompt_builder import (
    build_system_prompt,
    build_trade_parser_system_prompt,
    build_trade_parser_user_prompt_from_sample,
    build_user_prompt_from_sample,
)


@dataclass(slots=True)
class SFTExample:
    custom_id: str
    task: str
    npc_id: str
    scenario_id: str | None
    system_prompt: str
    user_prompt: str
    assistant_json: dict[str, Any]
    messages: list[dict[str, str]]


def coerce_sft_examples(rows: list[dict[str, Any]]) -> list[SFTExample]:
    return [SFTExample(**row) for row in rows]


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def merge_prompt_pack_with_teacher_outputs(
    prompt_rows: list[dict[str, Any]],
    teacher_rows: list[dict[str, Any]],
) -> list[SFTExample]:
    teacher_by_id = {row["custom_id"]: _normalize_teacher_row(row) for row in teacher_rows}
    examples: list[SFTExample] = []
    for prompt_row in prompt_rows:
        custom_id = prompt_row["custom_id"]
        teacher_payload = teacher_by_id.get(custom_id)
        if teacher_payload is None:
            continue
        metadata = prompt_row.get("metadata", {})
        assistant_text = json.dumps(teacher_payload, ensure_ascii=False)
        examples.append(
            SFTExample(
                custom_id=custom_id,
                task=prompt_row["task"],
                npc_id=str(metadata.get("npc_id", "")),
                scenario_id=metadata.get("scenario_id"),
                system_prompt=prompt_row["system_prompt"],
                user_prompt=prompt_row["user_prompt"],
                assistant_json=teacher_payload,
                messages=[
                    {"role": "system", "content": prompt_row["system_prompt"]},
                    {"role": "user", "content": prompt_row["user_prompt"]},
                    {"role": "assistant", "content": assistant_text},
                ],
            )
        )
    return examples


def merge_prompt_pack_with_teacher_outputs_runtime_dialogue(
    prompt_rows: list[dict[str, Any]],
    teacher_rows: list[dict[str, Any]],
) -> list[SFTExample]:
    teacher_by_id = {row["custom_id"]: _normalize_teacher_row(row) for row in teacher_rows}
    examples: list[SFTExample] = []
    for prompt_row in prompt_rows:
        if prompt_row.get("task") != "dialogue":
            continue
        custom_id = prompt_row["custom_id"]
        teacher_payload = teacher_by_id.get(custom_id)
        if teacher_payload is None:
            continue
        response = teacher_payload.get("response")
        if not isinstance(response, str) or not response.strip():
            continue
        sample = _extract_world_sample(prompt_row["user_prompt"])
        runtime_user_prompt = build_user_prompt_from_sample(sample)
        metadata = prompt_row.get("metadata", {})
        examples.append(
            SFTExample(
                custom_id=custom_id,
                task="dialogue_runtime",
                npc_id=str(metadata.get("npc_id", "")),
                scenario_id=metadata.get("scenario_id"),
                system_prompt=build_system_prompt(),
                user_prompt=runtime_user_prompt,
                assistant_json=teacher_payload,
                messages=[
                    {"role": "system", "content": build_system_prompt()},
                    {"role": "user", "content": runtime_user_prompt},
                    {"role": "assistant", "content": response.strip()},
                ],
            )
        )
        parser_target = sample.get("interaction_context", {}).get("trade_parse_target")
        if isinstance(parser_target, dict):
            parser_system_prompt = build_trade_parser_system_prompt()
            parser_user_prompt = build_trade_parser_user_prompt_from_sample(sample)
            examples.append(
                SFTExample(
                    custom_id=f"{custom_id}.trade_parser",
                    task="trade_parser_runtime",
                    npc_id=str(metadata.get("npc_id", "")),
                    scenario_id=metadata.get("scenario_id"),
                    system_prompt=parser_system_prompt,
                    user_prompt=parser_user_prompt,
                    assistant_json=dict(parser_target),
                    messages=[
                        {"role": "system", "content": parser_system_prompt},
                        {"role": "user", "content": parser_user_prompt},
                        {"role": "assistant", "content": json.dumps(parser_target, ensure_ascii=False)},
                    ],
                )
            )
    return examples


def split_sft_examples(
    examples: list[SFTExample],
    *,
    train_rows_target: int | None = None,
    eval_rows_target: int | None = None,
    eval_ratio: float = 0.08,
    seed: int = 7,
) -> tuple[list[SFTExample], list[SFTExample]]:
    if not examples:
        return [], []

    ordered = sorted(examples, key=lambda example: _stable_example_key(example.custom_id, seed))
    available = len(ordered)

    if train_rows_target is not None or eval_rows_target is not None:
        target_total = min(
            available,
            max(1, (train_rows_target or 0) + (eval_rows_target or 0)),
        )
        ordered = ordered[:target_total]
    total = len(ordered)
    if total == 1:
        return ordered, []

    if eval_rows_target is not None:
        eval_count = min(max(1, eval_rows_target), total - 1)
    else:
        eval_count = min(max(1, round(total * eval_ratio)), total - 1)

    if train_rows_target is not None:
        train_count = min(max(1, train_rows_target), total - eval_count)
        eval_count = min(eval_count, total - train_count)
    else:
        train_count = total - eval_count

    eval_examples = ordered[:eval_count]
    train_examples = ordered[eval_count : eval_count + train_count]
    if not train_examples:
        train_examples = ordered[eval_count:]
    return train_examples, eval_examples


def export_sft_jsonl(path: str | Path, examples: list[SFTExample]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(asdict(example), ensure_ascii=False) + "\n")
    return output_path


def export_sft_parquet(path: str | Path, examples: list[SFTExample]) -> Path:
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
        record["assistant_json"] = json.dumps(record["assistant_json"], ensure_ascii=False)
        record["messages"] = json.dumps(record["messages"], ensure_ascii=False)
        records.append(record)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(records), output_path)
    return output_path


def _normalize_teacher_row(row: dict[str, Any]) -> dict[str, Any]:
    if "assistant_json" in row and isinstance(row["assistant_json"], dict):
        return row["assistant_json"]
    if "output_json" in row and isinstance(row["output_json"], dict):
        return row["output_json"]
    for key in ("response_text", "output_text", "assistant_text", "response"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Teacher output for {row.get('custom_id')} is not valid JSON text.") from exc
    raise ValueError(f"Teacher row for {row.get('custom_id')} does not contain a supported payload.")


def _stable_example_key(custom_id: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{custom_id}".encode("utf-8")).hexdigest()


def _extract_world_sample(user_prompt: str) -> dict[str, Any]:
    marker = "World sample:"
    _, sample_text = user_prompt.split(marker, 1)
    return ast.literal_eval(sample_text.strip())
