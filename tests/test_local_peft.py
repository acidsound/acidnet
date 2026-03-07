import json
import sys
import types
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM

from acidnet.llm import DialogueContext
from acidnet.llm.local_peft import LocalPeftDialogueAdapter, _load_adapter_config, _resolve_model_loader
from acidnet.simulator import build_demo_setup


def _artifact_dir(name: str) -> Path:
    path = Path("data") / "test_artifacts" / "local_peft" / name
    path.mkdir(parents=True, exist_ok=True)
    return path


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


def test_load_adapter_config_returns_empty_dict_for_missing_file() -> None:
    missing_dir = _artifact_dir("missing")
    assert _load_adapter_config(str(missing_dir)) == {}


def test_resolve_model_loader_uses_adapter_auto_mapping(monkeypatch) -> None:
    module_name = "acidnet_test_fake_loader"
    fake_module = types.ModuleType(module_name)

    class FakeLoader:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

    fake_module.FakeLoader = FakeLoader
    monkeypatch.setitem(sys.modules, module_name, fake_module)

    adapter_dir = _artifact_dir("auto_mapping")
    (adapter_dir / "adapter_config.json").write_text(
        json.dumps(
            {
                "auto_mapping": {
                    "parent_library": module_name,
                    "base_model_class": "FakeLoader",
                }
            }
        ),
        encoding="utf-8",
    )

    assert _resolve_model_loader(str(adapter_dir)) is FakeLoader


def test_resolve_model_loader_falls_back_when_auto_mapping_is_invalid() -> None:
    adapter_dir = _artifact_dir("invalid_auto_mapping")
    (adapter_dir / "adapter_config.json").write_text(
        json.dumps(
            {
                "auto_mapping": {
                    "parent_library": "json",
                    "base_model_class": "JSONDecoder",
                }
            }
        ),
        encoding="utf-8",
    )

    assert _resolve_model_loader(str(adapter_dir)) is AutoModelForCausalLM


def test_local_peft_prepare_uses_bundle_loader(monkeypatch) -> None:
    class FakeTokenizer:
        def __len__(self) -> int:
            return 32000

    class FakeModel:
        device = "cuda:0"

    def fake_load_bundle(*, base_model: str, adapter_path: str, load_in_4bit: bool):
        assert base_model == "Qwen/Qwen3.5-4B"
        assert adapter_path == "data/adapters/demo"
        assert load_in_4bit is False
        return FakeTokenizer(), FakeModel()

    monkeypatch.setattr("acidnet.llm.local_peft._load_bundle", fake_load_bundle)

    adapter = LocalPeftDialogueAdapter(
        model="Qwen/Qwen3.5-4B",
        adapter_path="data/adapters/demo",
    )

    status = adapter.prepare()

    assert "Local dialogue model ready" in status
    assert "data/adapters/demo" not in status
    assert "demo" in status


def test_local_peft_generate_sanitizes_hidden_reasoning_and_sentence_limit(monkeypatch) -> None:
    class FakeTokenizer:
        eos_token_id = 0

        def apply_chat_template(self, messages, tokenize: bool, add_generation_prompt: bool, enable_thinking: bool) -> str:  # noqa: ANN001
            return "prompt"

        def __call__(self, prompt: str, return_tensors: str, truncation: bool, max_length: int) -> dict[str, torch.Tensor]:
            return {
                "input_ids": torch.tensor([[1, 2]], dtype=torch.long),
                "attention_mask": torch.tensor([[1, 1]], dtype=torch.long),
            }

        def decode(self, tokens, skip_special_tokens: bool) -> str:  # noqa: ANN001
            return "assistant: <think>check stock</think>\n\nI can spare bread if we settle the exchange. Do not wait too long."

    class FakeModel:
        device = "cpu"

        def generate(self, **kwargs) -> torch.Tensor:
            return torch.tensor([[1, 2, 3, 4]], dtype=torch.long)

    def fake_load_bundle(*, base_model: str, adapter_path: str, load_in_4bit: bool):
        assert base_model == "Qwen/Qwen3.5-4B"
        assert adapter_path == "data/adapters/demo"
        assert load_in_4bit is False
        return FakeTokenizer(), FakeModel()

    monkeypatch.setattr("acidnet.llm.local_peft._load_bundle", fake_load_bundle)

    adapter = LocalPeftDialogueAdapter(
        model="Qwen/Qwen3.5-4B",
        adapter_path="data/adapters/demo",
        temperature=0.0,
    )

    result = adapter.generate(_build_dialogue_context("Stay grounded. Reply with one short in-character sentence only."))

    assert result.text == "I can spare bread if we settle the exchange."
