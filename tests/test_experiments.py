from pathlib import Path

from experiments import run_count_to_infinity_demo, run_experiments
from topology import Topology


ROOT = Path(__file__).resolve().parents[1]


def test_main_experiments_are_reproducible_and_paths_differ(tmp_path):
    topology, config = Topology.from_json(ROOT / "config.json")
    first = run_experiments(topology, config, tmp_path / "first")
    second = run_experiments(topology, config, tmp_path / "second")
    assert first["records"] == second["records"]
    assert len(first["records"]) == 12
    assert (tmp_path / "first" / "summary.csv").is_file()
    assert first["phase_results"]["initial"][("Link State", "hop")][1]["path"] != (
        first["phase_results"]["initial"][("Link State", "etx")][1]["path"]
    )
    for name in ("convergence.png", "message_overhead.png", "path_quality.png", "topology.png"):
        assert (tmp_path / "first" / name).stat().st_size > 0


def test_count_to_infinity_is_observed_and_prevention_stops_increase():
    result = run_count_to_infinity_demo()
    no_prevention = result["none"]["changes"]
    assert any(change["cost"] > 3 for change in no_prevention)
    for mechanism in ("split_horizon", "poison_reverse"):
        costs = [
            change["cost"]
            for change in result[mechanism]["changes"]
            if change["cost"] != float("inf")
        ]
        assert not any(cost > 3 for cost in costs)
