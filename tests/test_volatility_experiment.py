import csv
import math
from pathlib import Path

import pytest

from link_state import LinkState
from metrics import path_etx
from topology import Topology
from volatility_experiment import (
    DEFAULT_SEED,
    FixedThresholdEtxSelector,
    LinkQualityVolatility,
    SCENARIOS,
    VolatilityAwareEtxSelector,
    VolatilitySettings,
    generate_quality_trace,
    run_volatility_experiment,
)


ROOT = Path(__file__).resolve().parents[1]


def small_topology() -> Topology:
    return Topology(
        ["A", "B", "C"],
        [
            {"u": "A", "v": "B", "forward": 0.5, "reverse": 0.5, "available": True},
            {"u": "A", "v": "C", "forward": 0.5, "reverse": 0.625, "available": True},
        ],
    )


def test_fixed_threshold_switches_at_inclusive_improvement_boundary():
    topology = small_topology()
    selector = FixedThresholdEtxSelector(0.25)
    assert selector.select(["A", "B"], topology) == ["A", "B"]
    topology.link("A", "C")["reverse"] = 2 / 3
    assert path_etx(["A", "B"], topology.links) == pytest.approx(4.0)
    assert path_etx(["A", "C"], topology.links) == pytest.approx(3.0)
    assert selector.select(["A", "C"], topology) == ["A", "C"]


def test_fixed_threshold_does_not_switch_below_improvement_boundary():
    topology = small_topology()
    selector = FixedThresholdEtxSelector(0.25)
    selector.select(["A", "B"], topology)
    assert selector.select(["A", "C"], topology) == ["A", "B"]
    assert selector.switches == 0


def test_volatility_is_ewma_of_relative_etx_change():
    estimator = LinkQualityVolatility(alpha=0.5)
    links = [{"u": "A", "v": "B", "forward": 0.5, "reverse": 0.5, "available": True}]
    assert estimator.observe(links) == 0
    links[0]["reverse"] = 0.625
    assert estimator.observe(links) == pytest.approx(0.1)
    links[0]["reverse"] = 0.625
    assert estimator.observe(links) == pytest.approx(0.05)


def test_volatility_threshold_is_bounded_and_stable_quality_lowers_it():
    settings = VolatilitySettings(
        minimum_threshold=0.02,
        maximum_threshold=0.4,
        ewma_alpha=1,
        volatility_scale=0.2,
    )
    selector = VolatilityAwareEtxSelector(settings)
    links = [{"u": "A", "v": "B", "forward": 0.5, "reverse": 0.5, "available": True}]
    selector.observe(links)
    stable_threshold = selector.threshold()
    links[0]["reverse"] = 0.05
    selector.observe(links)
    volatile_threshold = selector.threshold()
    assert stable_threshold == settings.minimum_threshold
    assert volatile_threshold == settings.maximum_threshold
    assert settings.minimum_threshold <= volatile_threshold <= settings.maximum_threshold


def test_link_quality_traces_are_reproducible_and_keep_probabilities_valid():
    topology, _ = Topology.from_json(ROOT / "config.json")
    first, events = generate_quality_trace(topology, "Failure and recovery", 731, rounds=16)
    second, second_events = generate_quality_trace(topology, "Failure and recovery", 731, rounds=16)
    other, _ = generate_quality_trace(topology, "High variability", 732, rounds=16)
    assert first == second
    assert events == second_events
    assert first != other
    assert events == [
        {"round": 6, "event": "failure", "u": "E", "v": "F"},
        {"round": 10, "event": "recovery", "u": "E", "v": "F"},
    ]
    for sample in first:
        for link in sample:
            assert 0 < link["forward"] <= 1
            assert 0 < link["reverse"] <= 1


def test_link_state_candidate_uses_computed_etx_path():
    topology, _ = Topology.from_json(ROOT / "config.json")
    protocol = LinkState(topology, "etx")
    protocol.run()
    path = protocol.path("A", "D")
    assert path == ["A", "E", "F", "D"]
    assert protocol._dijkstra("A")["D"].cost == pytest.approx(
        path_etx(path, topology.links)
    )


def test_experiment_reroutes_immediately_and_returns_after_failure_recovery(tmp_path):
    topology, config = Topology.from_json(ROOT / "config.json")
    result = run_volatility_experiment(
        topology,
        config,
        tmp_path,
        trials=1,
        seed=DEFAULT_SEED,
        rounds=16,
    )
    rows = [row for row in result["trials"] if row["scenario"] == "Failure and recovery"]
    assert len(rows) == 3
    assert all(row["failure_response_rounds"] == 0 for row in rows)
    assert all(row["recovery_response_rounds"] == 0 for row in rows)
    assert all(row["unavailable_route_rounds"] == 0 for row in rows)
    assert (tmp_path / "failure_recovery_response.png").stat().st_size > 0


def test_multi_trial_experiment_outputs_seeded_measures_and_graphs(tmp_path):
    topology, config = Topology.from_json(ROOT / "config.json")
    result = run_volatility_experiment(
        topology,
        config,
        tmp_path,
        trials=2,
        seed=100,
        rounds=12,
    )
    assert len(result["trials"]) == len(SCENARIOS) * 2 * 3
    assert len(result["aggregate"]) == len(SCENARIOS) * 3
    assert {row["seed"] for row in result["trials"]} == {100, 101}
    high_variability_rows = [
        row for row in result["timeline"]
        if row["scenario"] == "High variability" and row["seed"] == 100
    ]
    for round_number in range(12):
        round_rows = [
            row for row in high_variability_rows if row["round"] == round_number
        ]
        assert len({row["candidate_route"] for row in round_rows}) == 1
        assert len({row["link_state_messages_this_round"] for row in round_rows}) == 1
    for filename in (
        "trials.csv",
        "aggregate.csv",
        "route_timeline.csv",
        "route_switches.png",
        "path_etx.png",
        "route_timeline.png",
        "failure_recovery_response.png",
    ):
        assert (tmp_path / filename).stat().st_size > 0
    with (tmp_path / "trials.csv").open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == len(result["trials"])
    assert all(math.isfinite(float(row["cumulative_selected_etx"])) for row in rows)


def test_experiment_results_are_reproducible(tmp_path):
    topology, config = Topology.from_json(ROOT / "config.json")
    first = run_volatility_experiment(
        topology, config, tmp_path / "first", trials=1, seed=DEFAULT_SEED, rounds=12
    )
    second = run_volatility_experiment(
        topology, config, tmp_path / "second", trials=1, seed=DEFAULT_SEED, rounds=12
    )
    assert first["trials"] == second["trials"]
    assert first["aggregate"] == second["aggregate"]
