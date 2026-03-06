from acidnet.eval import run_model_gate


def test_heuristic_backend_passes_combined_model_gate() -> None:
    report = run_model_gate(dialogue_backend="heuristic", circulation_turns=60)

    assert report.gate_passed is True
    assert report.prompt_average_score >= 0.9
    assert report.circulation.circulation_score >= 0.6
    assert not report.gate_failures
