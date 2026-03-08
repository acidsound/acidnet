from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from urllib import request

from acidnet.llm.prompt_builder import (
    build_system_prompt,
    build_trade_parser_system_prompt,
    build_trade_parser_user_prompt,
    build_user_prompt,
    finalize_dialogue_text,
)
from acidnet.llm.protocols import DialogueContext, DialogueModelAdapter, DialogueResult
from acidnet.llm.trade_dialogue import TradeDialogueIntent, parse_trade_dialogue_intent_payload


@dataclass(slots=True)
class OpenAICompatDialogueAdapter(DialogueModelAdapter):
    model: str
    endpoint: str
    api_key_env: str = "OPENAI_API_KEY"
    temperature: float = 0.7
    top_p: float = 0.8
    top_k: int = 20
    min_p: float = 0.0
    presence_penalty: float = 1.5
    repetition_penalty: float = 1.0
    max_tokens: int = 96
    timeout_seconds: int = 30

    def prepare(self) -> str | None:
        return f"OpenAI-compatible dialogue endpoint ready: {self.model} @ {self.endpoint}"

    def generate(self, context: DialogueContext) -> DialogueResult:
        started_at = time.perf_counter()
        text = self._request_text(
            [
                {"role": "system", "content": build_system_prompt(context)},
                {"role": "user", "content": build_user_prompt(context)},
            ],
            temperature=self.temperature,
            top_p=self.top_p,
            top_k=self.top_k,
            min_p=self.min_p,
            presence_penalty=self.presence_penalty,
            repetition_penalty=self.repetition_penalty,
            max_tokens=self.max_tokens,
        )
        text = finalize_dialogue_text(text, context)
        if not text:
            raise RuntimeError("OpenAI-compatible server returned an empty dialogue response.")
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        return DialogueResult(text=text, adapter_name="openai_compat", latency_ms=round(latency_ms, 3))

    def parse_trade_intent(self, context: DialogueContext) -> TradeDialogueIntent | None:
        text = self._request_text(
            [
                {"role": "system", "content": build_trade_parser_system_prompt()},
                {"role": "user", "content": build_trade_parser_user_prompt(context)},
            ],
            temperature=0.0,
            top_p=1.0,
            top_k=0,
            min_p=0.0,
            presence_penalty=0.0,
            repetition_penalty=1.0,
            max_tokens=80,
        )
        return parse_trade_dialogue_intent_payload(text)

    def _request_text(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        top_p: float,
        top_k: int,
        min_p: float,
        presence_penalty: float,
        repetition_penalty: float,
        max_tokens: int,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "min_p": min_p,
            "presence_penalty": presence_penalty,
            "repeat_penalty": repetition_penalty,
            "max_tokens": max_tokens,
        }
        response_payload = self._request_payload(payload)
        return (
            response_payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

    def _request_payload(self, payload: dict[str, object]) -> dict[str, object]:
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        api_key = os.environ.get(self.api_key_env)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        http_request = request.Request(self.endpoint, data=body, headers=headers, method="POST")
        with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
