from acidnet.eval import run_circulation_eval
from acidnet.simulator import Simulation


def test_circulation_eval_reports_active_world_without_mass_starvation() -> None:
    simulation = Simulation.create_demo()

    report = run_circulation_eval(simulation, turns=120)

    assert report.turns == 120
    assert report.average_active_locations >= 4.0
    assert report.min_active_locations >= 3
    assert report.starving_npc_count <= 1
    assert report.circulation_score >= 0.6
    assert report.action_counts["work"] > 0
    assert report.action_counts["move"] > 0
