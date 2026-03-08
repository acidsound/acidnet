from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_model_gate
import run_prompt_only_baseline_eval
from acidnet.cli import build_parser as build_cli_parser
from acidnet.frontend.web_app import build_parser as build_web_parser
from acidnet.llm import DEFAULT_OPENAI_COMPAT_MODEL, EVAL_DIALOGUE_BACKENDS, RUNTIME_DIALOGUE_BACKENDS
from acidnet.llm.openai_compat import OpenAICompatDialogueAdapter
from acidnet.llm.rule_based import FallbackDialogueAdapter, build_dialogue_adapter


def test_runtime_dialogue_parsers_expose_only_promoted_backends() -> None:
    cli_parser = build_cli_parser()
    web_parser = build_web_parser()

    assert tuple(cli_parser._option_string_actions["--dialogue-backend"].choices) == RUNTIME_DIALOGUE_BACKENDS
    assert tuple(web_parser._option_string_actions["--dialogue-backend"].choices) == RUNTIME_DIALOGUE_BACKENDS
    assert "--dialogue-adapter-path" not in cli_parser._option_string_actions
    assert "--dialogue-adapter-path" not in web_parser._option_string_actions


def test_runtime_dialogue_parsers_reject_local_peft() -> None:
    cli_parser = build_cli_parser()
    web_parser = build_web_parser()

    with pytest.raises(SystemExit):
        cli_parser.parse_args(["--dialogue-backend", "local_peft"])

    with pytest.raises(SystemExit):
        web_parser.parse_args(["--dialogue-backend", "local_peft"])


def test_eval_dialogue_parsers_keep_local_peft_for_dev_and_parity() -> None:
    model_gate_parser = run_model_gate.build_parser()
    prompt_only_parser = run_prompt_only_baseline_eval.build_parser()

    assert tuple(model_gate_parser._option_string_actions["--dialogue-backend"].choices) == EVAL_DIALOGUE_BACKENDS
    assert tuple(prompt_only_parser._option_string_actions["--dialogue-backend"].choices) == EVAL_DIALOGUE_BACKENDS
    assert model_gate_parser.parse_args(["--dialogue-backend", "local_peft"]).dialogue_backend == "local_peft"
    assert prompt_only_parser.parse_args(["--dialogue-backend", "local_peft"]).dialogue_backend == "local_peft"


def test_openai_compat_default_model_alias_matches_promoted_runtime() -> None:
    adapter = build_dialogue_adapter("openai_compat")

    assert isinstance(adapter, FallbackDialogueAdapter)
    assert isinstance(adapter.primary, OpenAICompatDialogueAdapter)
    assert adapter.primary.model == DEFAULT_OPENAI_COMPAT_MODEL


def test_promoted_llama_server_launchers_disable_reasoning() -> None:
    run_llama_server = (ROOT / "run_llama_server.ps1").read_text(encoding="utf-8")
    run_local_qwen_dev_loop = (ROOT / "run_local_qwen_dev_loop.ps1").read_text(encoding="utf-8")

    for content in (run_llama_server, run_local_qwen_dev_loop):
        assert '"--reasoning-format", "none"' in content
        assert '"--reasoning-budget", "0"' in content
