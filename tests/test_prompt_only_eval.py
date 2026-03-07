from acidnet.eval import run_prompt_only_baseline_eval
from acidnet.eval.prompt_only import PromptOnlyEvalRow, _evaluate_response, count_backend_fallback_rows
from acidnet.simulator import Simulation


def _prompt_row(*, backend: str, adapter_name: str) -> PromptOnlyEvalRow:
    return PromptOnlyEvalRow(
        npc_id="npc.test",
        npc_name="Test NPC",
        interaction_mode="talk",
        interaction_case="scene_talk",
        player_prompt="What is going on around here?",
        response_text="The square stays noisy today.",
        backend=backend,
        adapter_name=adapter_name,
        latency_ms=0.0,
        score=1.0,
        passed_checks=["non_empty"],
        failed_checks=[],
    )


def test_repeated_talks_make_npc_treat_player_as_familiar() -> None:
    simulation = Simulation.create_demo()

    simulation.handle_command("talk neri")
    reply = simulation.probe_npc_dialogue(
        "npc.neri",
        interaction_mode="talk",
        player_prompt="What is going on around here?",
    )

    assert "not entirely new" in reply.lower() or "recognizes you" in reply.lower()


def test_prompt_only_eval_produces_rows_for_demo_world() -> None:
    rows = run_prompt_only_baseline_eval(dialogue_backend="heuristic")

    assert rows
    assert all(row.response_text for row in rows)
    assert any(row.interaction_mode == "direct_say" for row in rows)
    assert any(row.interaction_case == "origin_direct" for row in rows)
    assert any(row.interaction_case == "identity_direct" for row in rows)
    assert any(row.interaction_case == "hunger_direct" for row in rows)
    assert any(row.interaction_mode == "rumor_request" for row in rows)
    assert all(row.adapter_name == "rule_based" for row in rows)
    assert all(row.latency_ms == 0.0 for row in rows)
    assert all(0.0 <= row.score <= 1.0 for row in rows)


def test_count_backend_fallback_rows_treats_local_peft_like_openai_compat() -> None:
    rows = [
        _prompt_row(backend="heuristic", adapter_name="rule_based"),
        _prompt_row(backend="openai_compat", adapter_name="openai_compat"),
        _prompt_row(backend="local_peft", adapter_name="rule_based"),
    ]

    assert count_backend_fallback_rows(rows) == 1


def test_rumor_request_accepts_any_known_rumor_match() -> None:
    simulation = Simulation.create_demo()
    npc = simulation.npcs["npc.hobb"]
    assert len(npc.known_rumor_ids) >= 2
    second_rumor = simulation.rumors[npc.known_rumor_ids[1]]

    passed, failed = _evaluate_response(
        simulation,
        npc.npc_id,
        "rumor_request",
        "rumor_request_known",
        "Have you heard any useful rumors?",
        second_rumor.content,
    )

    assert "mentions_known_rumor" in passed
    assert "mentions_known_rumor" not in failed


def test_hunger_request_does_not_treat_tools_as_food() -> None:
    simulation = Simulation.create_demo()
    npc = simulation.npcs["npc.doran"]

    passed, failed = _evaluate_response(
        simulation,
        npc.npc_id,
        "direct_say",
        "hunger_direct",
        "I am hungry.",
        "If you can pay, I still have tool x2 nearby. Do not wait until the shelves thin further.",
    )

    assert "answers_hunger_request" not in passed
    assert "answers_hunger_request" in failed


def test_hunger_request_flags_invented_food_stock() -> None:
    simulation = Simulation.create_demo()
    npc = simulation.npcs["npc.doran"]

    passed, failed = _evaluate_response(
        simulation,
        npc.npc_id,
        "direct_say",
        "hunger_direct",
        "I am hungry.",
        "If you can pay, I still have stew on hand. Do not wait until the shelves thin further.",
    )

    assert "does_not_invent_food_stock" not in passed
    assert "does_not_invent_food_stock" in failed


def test_food_trade_request_accepts_plain_redirect_when_vendor_has_no_edible_goods() -> None:
    simulation = Simulation.create_demo()
    npc = simulation.npcs["npc.doran"]

    passed, failed = _evaluate_response(
        simulation,
        npc.npc_id,
        "trade_request",
        "trade_request_stock",
        "I need food. What can you sell me right now?",
        "I do not have food to sell from Red Anvil Smithy right now. Try the bakery or the tavern before the shelves thin further.",
    )

    assert "answers_food_trade_without_fake_stock" in passed
    assert "does_not_invent_food_stock" in passed
    assert "answers_food_trade_without_fake_stock" not in failed
    assert "does_not_invent_food_stock" not in failed
