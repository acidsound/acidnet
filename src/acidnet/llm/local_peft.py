from __future__ import annotations

import time
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from acidnet.llm.prompt_builder import build_system_prompt, build_user_prompt
from acidnet.llm.protocols import DialogueContext, DialogueModelAdapter, DialogueResult


def _ensure_windows_shims_on_path() -> str | None:
    if os.name != "nt":
        return None
    shim_dir = Path(__file__).resolve().parents[3] / "tools" / "windows_shims"
    current_path = os.environ.get("PATH", "")
    shim_str = str(shim_dir)
    if shim_str.lower() not in current_path.lower():
        os.environ["PATH"] = shim_str + os.pathsep + current_path
    return shim_str


_ensure_windows_shims_on_path()

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

_MODEL_CACHE: dict[tuple[str, str, bool], tuple[Any, Any]] = {}


@dataclass(slots=True)
class LocalPeftDialogueAdapter(DialogueModelAdapter):
    model: str
    adapter_path: str
    temperature: float = 0.35
    max_tokens: int = 96
    max_input_tokens: int = 4096
    load_in_4bit: bool = False

    def generate(self, context: DialogueContext) -> DialogueResult:
        tokenizer, model = _load_bundle(
            base_model=self.model,
            adapter_path=self.adapter_path,
            load_in_4bit=self.load_in_4bit,
        )
        started_at = time.perf_counter()
        messages = [
            {"role": "system", "content": build_system_prompt(context)},
            {"role": "user", "content": build_user_prompt(context)},
        ]
        prompt = _build_prompt(tokenizer, messages)
        encoded = tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_input_tokens,
        )
        device = getattr(model, "device", torch.device("cuda" if torch.cuda.is_available() else "cpu"))
        encoded = {key: value.to(device) for key, value in encoded.items()}

        generation_kwargs: dict[str, Any] = {
            "max_new_tokens": max(8, min(self.max_tokens, 256)),
            "pad_token_id": tokenizer.eos_token_id,
            "eos_token_id": tokenizer.eos_token_id,
        }
        if self.temperature > 0:
            generation_kwargs["do_sample"] = True
            generation_kwargs["temperature"] = self.temperature
        else:
            generation_kwargs["do_sample"] = False

        with torch.inference_mode():
            output = model.generate(**encoded, **generation_kwargs)
        generated_tokens = output[0][encoded["input_ids"].shape[1] :]
        text = _sanitize_generated_text(tokenizer.decode(generated_tokens, skip_special_tokens=True))
        if not text:
            raise RuntimeError("The local PEFT adapter generated an empty dialogue response.")
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        return DialogueResult(text=text, adapter_name="local_peft", latency_ms=round(latency_ms, 3))


def _load_bundle(*, base_model: str, adapter_path: str, load_in_4bit: bool) -> tuple[Any, Any]:
    resolved_adapter_path = str(Path(adapter_path))
    cache_key = (base_model, resolved_adapter_path, load_in_4bit)
    cached = _MODEL_CACHE.get(cache_key)
    if cached is not None:
        return cached

    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float16
    quantization_config = None
    if load_in_4bit:
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=dtype,
            bnb_4bit_quant_type="nf4",
        )

    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=dtype,
        device_map="auto" if torch.cuda.is_available() else None,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
        quantization_config=quantization_config,
    )
    model = PeftModel.from_pretrained(model, resolved_adapter_path)
    model.eval()
    _MODEL_CACHE[cache_key] = (tokenizer, model)
    return tokenizer, model


def _build_prompt(tokenizer: Any, messages: list[dict[str, str]]) -> str:
    if hasattr(tokenizer, "apply_chat_template"):
        try:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except Exception:
            pass
    return "\n".join(f"{item['role']}: {item['content']}" for item in messages) + "\nassistant:"


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
