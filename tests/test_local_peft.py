import json
import sys
import types

from transformers import AutoModelForCausalLM

from acidnet.llm.local_peft import _load_adapter_config, _resolve_model_loader


def test_load_adapter_config_returns_empty_dict_for_missing_file(tmp_path) -> None:
    assert _load_adapter_config(str(tmp_path)) == {}


def test_resolve_model_loader_uses_adapter_auto_mapping(tmp_path, monkeypatch) -> None:
    module_name = "acidnet_test_fake_loader"
    fake_module = types.ModuleType(module_name)

    class FakeLoader:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

    fake_module.FakeLoader = FakeLoader
    monkeypatch.setitem(sys.modules, module_name, fake_module)

    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir()
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


def test_resolve_model_loader_falls_back_when_auto_mapping_is_invalid(tmp_path) -> None:
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir()
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
