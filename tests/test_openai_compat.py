import json

from acidnet.llm import DialogueContext
from acidnet.llm.openai_compat import OpenAICompatDialogueAdapter
from acidnet.simulator import build_demo_setup


def _build_dialogue_context(system_prompt: str) -> DialogueContext:
    setup = build_demo_setup()
    npc = setup.npcs["npc.neri"]
    return DialogueContext(
        npc=npc,
        persona=setup.personas[npc.persona_id],
        player=setup.player,
        world=setup.world,
        location=setup.world.locations[npc.location_id],
        interaction_mode="direct_say",
        player_prompt="Where did you come from?",
        system_prompt=system_prompt,
    )


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_openai_compat_generate_sanitizes_hidden_reasoning_and_sentence_limit(monkeypatch) -> None:
    def fake_urlopen(http_request, timeout: int):  # noqa: ANN001
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                "```json\n"
                                '{"response":"assistant: Thinking Process: answer the origin question directly.\\n\\n'
                                'I keep close to Market Square. The square hears everything."}\n'
                                "```"
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("acidnet.llm.openai_compat.request.urlopen", fake_urlopen)

    adapter = OpenAICompatDialogueAdapter(
        model="demo-model",
        endpoint="http://127.0.0.1:8000/v1/chat/completions",
        temperature=0.0,
    )

    result = adapter.generate(_build_dialogue_context("Stay grounded. Reply with one short in-character sentence only."))

    assert result.text == "I keep close to Market Square."
    assert result.adapter_name == "openai_compat"


def test_openai_compat_generate_sends_qwen_non_thinking_sampling_defaults(monkeypatch) -> None:
    captured_payload: dict[str, object] = {}

    def fake_urlopen(http_request, timeout: int):  # noqa: ANN001
        nonlocal captured_payload
        captured_payload = json.loads(http_request.data.decode("utf-8"))
        return _FakeResponse({"choices": [{"message": {"content": "I keep close to Market Square."}}]})

    monkeypatch.setattr("acidnet.llm.openai_compat.request.urlopen", fake_urlopen)

    adapter = OpenAICompatDialogueAdapter(
        model="demo-model",
        endpoint="http://127.0.0.1:8000/v1/chat/completions",
    )

    adapter.generate(_build_dialogue_context("Stay grounded. Reply with one short in-character sentence only."))

    assert captured_payload["temperature"] == 0.7
    assert captured_payload["top_p"] == 0.8
    assert captured_payload["top_k"] == 20
    assert captured_payload["min_p"] == 0.0
    assert captured_payload["presence_penalty"] == 1.5
    assert captured_payload["repeat_penalty"] == 1.0
