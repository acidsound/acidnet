from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acidnet.training.windows_env import ensure_windows_shims_on_path

ensure_windows_shims_on_path()

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


@dataclass(slots=True)
class ServerState:
    model_alias: str
    tokenizer: Any
    model: Any
    max_input_tokens: int
    default_max_new_tokens: int
    default_temperature: float


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Serve a fine-tuned Qwen LoRA adapter behind an OpenAI-compatible chat endpoint for development and evaluation."
    )
    parser.add_argument("--adapter-path", required=True, help="Path to the fine-tuned LoRA adapter directory.")
    parser.add_argument("--base-model", default="Qwen/Qwen3.5-4B", help="Base model used for the adapter.")
    parser.add_argument("--model-alias", default="acidnet-qwen3.5-4b-lora", help="Model id exposed over the HTTP API.")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind host.")
    parser.add_argument("--port", type=int, default=8001, help="HTTP bind port.")
    parser.add_argument("--max-input-tokens", type=int, default=4096, help="Maximum prompt tokens retained before generation.")
    parser.add_argument("--max-new-tokens", type=int, default=96, help="Default completion token budget.")
    parser.add_argument("--temperature", type=float, default=0.35, help="Default generation temperature.")
    parser.add_argument("--load-in-4bit", action="store_true", help="Load the base model in 4-bit for lower VRAM usage.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    state = _load_server_state(args)
    server = ThreadingHTTPServer((args.host, args.port), _build_handler(state))
    print(f"Adapter server ready at http://{args.host}:{args.port}/v1/chat/completions")
    print(f"Model alias: {state.model_alias}")
    print(f"Adapter path: {args.adapter_path}")
    print("Use llama-server with the promoted Q4 GGUF runtime for deployment-facing simulator runs.")
    server.serve_forever()


def _load_server_state(args: argparse.Namespace) -> ServerState:
    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float16
    quantization_config = None
    if args.load_in_4bit:
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=dtype,
            bnb_4bit_quant_type="nf4",
        )

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=dtype,
        device_map="auto" if torch.cuda.is_available() else None,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
        quantization_config=quantization_config,
    )
    model = PeftModel.from_pretrained(model, args.adapter_path)
    model.eval()

    return ServerState(
        model_alias=args.model_alias,
        tokenizer=tokenizer,
        model=model,
        max_input_tokens=args.max_input_tokens,
        default_max_new_tokens=args.max_new_tokens,
        default_temperature=args.temperature,
    )


def _build_handler(state: ServerState) -> type[BaseHTTPRequestHandler]:
    class AdapterHandler(BaseHTTPRequestHandler):
        server_version = "AcidnetAdapterServer/0.1"

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/v1/models":
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "object": "list",
                        "data": [
                            {
                                "id": state.model_alias,
                                "object": "model",
                                "owned_by": "acidnet",
                            }
                        ],
                    },
                )
                return
            self._write_json(HTTPStatus.NOT_FOUND, {"error": {"message": "Not found"}})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/chat/completions":
                self._write_json(HTTPStatus.NOT_FOUND, {"error": {"message": "Not found"}})
                return

            try:
                payload = self._read_json()
                messages = payload.get("messages", [])
                prompt = _build_prompt(state.tokenizer, messages)
                text = _generate_text(
                    state,
                    prompt=prompt,
                    max_new_tokens=int(payload.get("max_tokens", state.default_max_new_tokens)),
                    temperature=float(payload.get("temperature", state.default_temperature)),
                )
                response = {
                    "id": f"chatcmpl-{uuid4().hex}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": payload.get("model") or state.model_alias,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": text},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                }
                self._write_json(HTTPStatus.OK, response)
            except Exception as exc:  # pragma: no cover - server-side runtime path
                self._write_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": {"message": str(exc)}},
                )

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def _read_json(self) -> dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            return json.loads(raw_body.decode("utf-8")) if raw_body else {}

        def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return AdapterHandler


def _build_prompt(tokenizer: Any, messages: list[dict[str, Any]]) -> str:
    normalized_messages = [
        {"role": str(message.get("role", "user")), "content": _coerce_content(message.get("content", ""))}
        for message in messages
    ]
    if hasattr(tokenizer, "apply_chat_template"):
        try:
            return tokenizer.apply_chat_template(
                normalized_messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except Exception:
            pass
    return "\n".join(f"{item['role']}: {item['content']}" for item in normalized_messages) + "\nassistant:"


def _coerce_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return " ".join(part for part in parts if part)
    return str(content)


def _generate_text(
    state: ServerState,
    *,
    prompt: str,
    max_new_tokens: int,
    temperature: float,
) -> str:
    tokenizer = state.tokenizer
    model = state.model
    encoded = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=state.max_input_tokens,
    )
    device = getattr(model, "device", torch.device("cuda" if torch.cuda.is_available() else "cpu"))
    encoded = {key: value.to(device) for key, value in encoded.items()}

    generation_kwargs: dict[str, Any] = {
        "max_new_tokens": max(8, min(max_new_tokens, 256)),
        "pad_token_id": tokenizer.eos_token_id,
        "eos_token_id": tokenizer.eos_token_id,
    }
    if temperature > 0:
        generation_kwargs["do_sample"] = True
        generation_kwargs["temperature"] = temperature
    else:
        generation_kwargs["do_sample"] = False

    with torch.inference_mode():
        output = model.generate(**encoded, **generation_kwargs)
    generated_tokens = output[0][encoded["input_ids"].shape[1] :]
    text = _sanitize_generated_text(tokenizer.decode(generated_tokens, skip_special_tokens=True))
    if not text:
        raise RuntimeError("The adapter server generated an empty response.")
    return text


def _sanitize_generated_text(text: str) -> str:
    cleaned = text.strip()
    if "<think>" in cleaned and "</think>" in cleaned:
        _, cleaned = cleaned.split("</think>", 1)
        cleaned = cleaned.strip()
    if cleaned.lower().startswith("thinking process:"):
        parts = cleaned.split("\n\n")
        cleaned = parts[-1].strip() if parts else ""
    if cleaned.startswith("1.") and "\n\n" in cleaned:
        cleaned = cleaned.split("\n\n")[-1].strip()
    return cleaned


if __name__ == "__main__":
    main()
