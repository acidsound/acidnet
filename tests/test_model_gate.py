from acidnet.eval import run_model_gate
from acidnet.eval.circulation import CirculationReport
from acidnet.eval.prompt_only import PromptOnlyEvalRow


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
        latency_ms=10.0,
        score=1.0,
        passed_checks=["non_empty"],
        failed_checks=[],
    )


def _stable_circulation_report() -> CirculationReport:
    return CirculationReport(
        turns=1,
        average_active_locations=5.0,
        min_active_locations=4,
        max_active_locations=5,
        peak_location_occupancy=3,
        peak_hunger_seen=40.0,
        average_final_hunger=22.0,
        starving_npc_count=0,
        zero_money_npc_count=0,
        scarcity_index=0.9,
        circulation_score=0.9,
        action_counts={},
        final_location_counts={},
        final_hunger_by_npc={},
        final_money_by_npc={},
        flags=[],
    )


def test_heuristic_backend_passes_combined_model_gate() -> None:
    report = run_model_gate(dialogue_backend="heuristic", circulation_turns=60)

    assert report.gate_passed is True
    assert report.prompt_average_score >= 0.9
    assert report.prompt_average_latency_ms == 0.0
    assert report.prompt_fallback_rows == 0
    assert report.prompt_adapter_names == ["rule_based"]
    assert report.circulation.circulation_score >= 0.6
    assert not report.gate_failures


def test_local_peft_fallback_rows_fail_combined_model_gate(monkeypatch) -> None:
    rows = [_prompt_row(backend="local_peft", adapter_name="rule_based") for _ in range(3)]

    def fake_run_prompt_only_baseline_eval(**kwargs):
        return rows

    def fake_run_circulation_eval(simulation, *, turns: int):
        return _stable_circulation_report()

    class FakeSimulation:
        @staticmethod
        def create_demo(**kwargs):
            return object()

    monkeypatch.setattr("acidnet.eval.model_gate.run_prompt_only_baseline_eval", fake_run_prompt_only_baseline_eval)
    monkeypatch.setattr("acidnet.eval.model_gate.run_circulation_eval", fake_run_circulation_eval)
    monkeypatch.setattr("acidnet.eval.model_gate.Simulation", FakeSimulation)

    report = run_model_gate(
        dialogue_backend="local_peft",
        dialogue_adapter_path="data/adapters/demo",
        circulation_turns=1,
    )

    assert report.prompt_fallback_rows == 3
    assert "too_many_prompt_fallbacks" in report.gate_failures
    assert report.gate_passed is False
