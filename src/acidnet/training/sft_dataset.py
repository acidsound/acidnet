from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


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


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
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
