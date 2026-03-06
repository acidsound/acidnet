from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from urllib import request

from acidnet.llm.prompt_builder import build_system_prompt, build_user_prompt
from acidnet.llm.protocols import DialogueContext, DialogueModelAdapter, DialogueResult


@dataclass(slots=True)
class OpenAICompatDialogueAdapter(DialogueModelAdapter):
    model: str
    endpoint: str
    api_key_env: str = "OPENAI_API_KEY"
    temperature: float = 0.35
    max_tokens: int = 96
    timeout_seconds: int = 30

    def prepare(self) -> str | None:
        return f"OpenAI-compatible dialogue endpoint ready: {self.model} @ {self.endpoint}"

    def generate(self, context: DialogueContext) -> DialogueResult:
        started_at = time.perf_counter()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": build_system_prompt(context)},
                {"role": "user", "content": build_user_prompt(context)},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        api_key = os.environ.get(self.api_key_env)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        http_request = request.Request(self.endpoint, data=body, headers=headers, method="POST")
        with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
            response_payload = json.loads(response.read().decode("utf-8"))

        text = (
            response_payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not text:
            raise RuntimeError("OpenAI-compatible server returned an empty dialogue response.")
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        return DialogueResult(text=text, adapter_name="openai_compat", latency_ms=round(latency_ms, 3))
