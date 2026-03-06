from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class OpenAIBatchRequest:
    custom_id: str
    method: str
    url: str
    body: dict[str, Any]


@dataclass(slots=True)
class TeacherOutputRow:
    custom_id: str
    assistant_json: dict[str, Any]
    metadata: dict[str, Any]


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_openai_batch_requests(
    prompt_rows: list[dict[str, Any]],
    *,
    model: str,
    max_output_tokens: int = 512,
) -> list[OpenAIBatchRequest]:
    requests: list[OpenAIBatchRequest] = []
    for row in prompt_rows:
        requests.append(
            OpenAIBatchRequest(
                custom_id=row["custom_id"],
                method="POST",
                url="/v1/responses",
                body={
                    "model": model,
                    "instructions": row["system_prompt"],
                    "input": row["user_prompt"],
                    "max_output_tokens": max_output_tokens,
                },
            )
        )
    return requests


def export_openai_batch_jsonl(path: str | Path, requests: list[OpenAIBatchRequest]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for request in requests:
            handle.write(json.dumps(asdict(request), ensure_ascii=False) + "\n")
    return output_path


def normalize_openai_batch_output(batch_rows: list[dict[str, Any]]) -> list[TeacherOutputRow]:
    normalized: list[TeacherOutputRow] = []
    for row in batch_rows:
        custom_id = row["custom_id"]
        response_body = row.get("response", {}).get("body", {})
        text = _extract_response_text(response_body)
        assistant_json = json.loads(text)
        normalized.append(
            TeacherOutputRow(
                custom_id=custom_id,
                assistant_json=assistant_json,
                metadata={
                    "status_code": row.get("response", {}).get("status_code"),
                    "request_id": row.get("response", {}).get("request_id"),
                    "error": row.get("error"),
                },
            )
        )
    return normalized


def export_teacher_output_jsonl(path: str | Path, rows: list[TeacherOutputRow]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")
    return output_path


def _extract_response_text(response_body: dict[str, Any]) -> str:
    output = response_body.get("output", [])
    for item in output:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                text = content.get("text", "").strip()
                if text:
                    return text
    raise ValueError("Could not extract output_text from OpenAI batch response row.")
