from acidnet.engine import Simulation
from acidnet.eval import SimulationMonkeyRunner


def test_monkey_runner_executes_deterministic_steps_without_breaking_invariants() -> None:
    simulation = Simulation.create_demo()
    runner = SimulationMonkeyRunner(simulation, seed=13)

    report = runner.run_steps(25)

    assert report.steps_executed == 25
    assert report.final_player_location in simulation.world.locations
    assert 0.0 <= report.final_player_hunger <= 100.0
    assert report.steps
    assert all(step.command for step in report.steps)
