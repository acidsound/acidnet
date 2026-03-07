import json

from acidnet.eval.circulation import CirculationReport
from acidnet.eval.model_gate import run_model_gate
from acidnet.eval.prompt_only import PromptOnlyEvalRow
from acidnet.llm import DialogueContext, DialogueResult, FallbackDialogueAdapter
from acidnet.llm.openai_compat import OpenAICompatDialogueAdapter
from acidnet.llm.rule_based import RuleBasedDialogueAdapter
from acidnet.simulator import build_demo_setup


def _build_dialogue_context(system_prompt: str) -> DialogueContext:
    setup = build_demo_setup()
    npc = setup.npcs["npc.hobb"]
    return DialogueContext(
        npc=npc,
        persona=setup.personas[npc.persona_id],
        player=setup.player,
        world=setup.world,
        location=setup.world.locations[npc.location_id],
        interaction_mode="talk",
        player_prompt="What is going on around here?",
        system_prompt=system_prompt,
        visible_rumors=[setup.rumors[rumor_id] for rumor_id in npc.known_rumor_ids[:1]],
    )


def test_openai_compat_generate_sanitizes_hidden_reasoning_and_sentence_limit(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            payload = {
                "choices": [
                    {
                        "message": {
                            "content": "<think>check stock</think>\n\nBread is still on my shelf. Come quickly before the ovens cool."
                        }
                    }
                ]
            }
            return json.dumps(payload).encode("utf-8")

    def fake_urlopen(http_request, timeout):  # noqa: ANN001
        return FakeResponse()

    monkeypatch.setattr("acidnet.llm.openai_compat.request.urlopen", fake_urlopen)

    adapter = OpenAICompatDialogueAdapter(
        model="demo-model",
        endpoint="http://127.0.0.1:8000/v1/chat/completions",
        temperature=0.0,
    )

    result = adapter.generate(_build_dialogue_context("Stay grounded. Reply with one short in-character sentence only."))

    assert result.text == "Bread is still on my shelf."


def test_fallback_dialogue_adapter_forwards_temperature_to_primary() -> None:
    class DummyPrimaryAdapter:
        def __init__(self) -> None:
            self.temperature = 0.35

        def prepare(self) -> str | None:
            return "ready"

        def generate(self, context: DialogueContext) -> DialogueResult:
            return DialogueResult(text="ready", adapter_name="dummy")

    primary = DummyPrimaryAdapter()
    adapter = FallbackDialogueAdapter(primary=primary, fallback=RuleBasedDialogueAdapter())

    assert adapter.temperature == 0.35

    adapter.temperature = 0.0

    assert primary.temperature == 0.0


def test_model_gate_counts_local_peft_fallback_rows(monkeypatch) -> None:
    rows = [
        PromptOnlyEvalRow(
            npc_id=f"npc.{index}",
            npc_name=f"NPC {index}",
            interaction_mode="talk",
            interaction_case="scene_talk",
            player_prompt="What is going on around here?",
            response_text="Fallback reply.",
            backend="local_peft",
            adapter_name="rule_based",
            latency_ms=0.0,
            score=1.0,
            passed_checks=["non_empty"],
            failed_checks=[],
        )
        for index in range(3)
    ]

    circulation = CirculationReport(
        turns=1,
        average_active_locations=5.0,
        min_active_locations=4,
        max_active_locations=5,
        peak_location_occupancy=2,
        peak_hunger_seen=40.0,
        average_final_hunger=30.0,
        starving_npc_count=0,
        zero_money_npc_count=0,
        scarcity_index=1.0,
        circulation_score=0.9,
        action_counts={},
        final_location_counts={},
        final_hunger_by_npc={},
        final_money_by_npc={},
        flags=[],
    )

    monkeypatch.setattr("acidnet.eval.model_gate.run_prompt_only_baseline_eval", lambda **kwargs: rows)
    monkeypatch.setattr("acidnet.eval.model_gate.run_circulation_eval", lambda simulation, turns: circulation)

    report = run_model_gate(
        dialogue_backend="local_peft",
        dialogue_model="Qwen/Qwen3.5-4B",
        dialogue_adapter_path="data/adapters/demo",
        circulation_turns=1,
    )

    assert report.prompt_fallback_rows == 3
    assert "too_many_prompt_fallbacks" in report.gate_failures
