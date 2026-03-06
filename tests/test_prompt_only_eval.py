from acidnet.engine import Simulation
from acidnet.eval import run_prompt_only_baseline_eval


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
    assert any(row.interaction_mode == "rumor_request" for row in rows)
    assert all(0.0 <= row.score <= 1.0 for row in rows)
