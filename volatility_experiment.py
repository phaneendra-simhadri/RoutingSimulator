"""Dynamic-link-quality experiment for source-to-destination ETX route selection."""

from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from link_state import LinkState
from metrics import etx, path_etx
from topology import Topology


STRATEGIES = ("Standard ETX", "Fixed-threshold ETX", "Volatility-aware ETX")
SCENARIOS = (
    "Low variability",
    "High variability",
    "Gradual deterioration",
    "Sudden severe deterioration",
    "Failure and recovery",
)
DEFAULT_ROUNDS = 80
DEFAULT_TRIALS = 30
DEFAULT_SEED = 20261028


@dataclass(frozen=True)
class VolatilitySettings:
    fixed_threshold: float = 0.10
    minimum_threshold: float = 0.02
    maximum_threshold: float = 0.45
    ewma_alpha: float = 0.30
    volatility_scale: float = 0.08

    def __post_init__(self) -> None:
        if not 0 <= self.fixed_threshold < 1:
            raise ValueError("fixed_threshold must be in [0, 1)")
        if not 0 <= self.minimum_threshold <= self.maximum_threshold < 1:
            raise ValueError("threshold bounds must satisfy 0 <= minimum <= maximum < 1")
        if not 0 < self.ewma_alpha <= 1:
            raise ValueError("ewma_alpha must be in (0, 1]")
        if not math.isfinite(self.volatility_scale) or self.volatility_scale <= 0:
            raise ValueError("volatility_scale must be finite and positive")


class LinkQualityVolatility:
    """EWMA of mean relative ETX changes on links available in both samples."""

    def __init__(self, alpha: float):
        if not 0 < alpha <= 1:
            raise ValueError("alpha must be in (0, 1]")
        self.alpha = alpha
        self.value = 0.0
        self._previous: dict[frozenset[str], float] | None = None

    def observe(self, links: Iterable[dict[str, Any]]) -> float:
        current = {
            frozenset((str(link["u"]), str(link["v"]))):
            etx(float(link["forward"]), float(link["reverse"]))
            for link in links
            if bool(link["available"])
        }
        if self._previous is not None:
            changes = [
                min(1.0, abs(current[edge] - previous) / previous)
                for edge, previous in self._previous.items()
                if edge in current
            ]
            if changes:
                observation = statistics.fmean(changes)
                self.value = self.alpha * observation + (1 - self.alpha) * self.value
        self._previous = current
        return self.value


class RouteSelector:
    """Selects among Link State candidate paths, independently of path calculation."""

    def __init__(self) -> None:
        self.path: list[str] | None = None
        self.switches = 0
        self._observed = False

    def threshold(self) -> float:
        return 0.0

    def _accept_candidate(self, current_cost: float, candidate_cost: float) -> bool:
        return candidate_cost < current_cost

    def select(
        self,
        candidate: list[str] | None,
        topology: Topology,
    ) -> list[str] | None:
        current_cost = path_etx(self.path, topology.links) if self.path is not None else math.inf
        candidate_cost = path_etx(candidate, topology.links) if candidate is not None else math.inf
        if not math.isfinite(current_cost):
            if self.path is not None:
                self._change(candidate)
            elif candidate is not None:
                self._change(candidate)
            self._observed = True
            return self.path
        if candidate is not None and candidate != self.path:
            if self._accept_candidate(current_cost, candidate_cost):
                self._change(candidate)
        self._observed = True
        return self.path

    def _change(self, candidate: list[str] | None) -> None:
        if self._observed:
            self.switches += 1
        self.path = list(candidate) if candidate is not None else None


class StandardEtxSelector(RouteSelector):
    """Always use the currently least-ETX Link State candidate when it is usable."""

    def _accept_candidate(self, current_cost: float, candidate_cost: float) -> bool:
        return candidate_cost < current_cost


class FixedThresholdEtxSelector(RouteSelector):
    """Switch only when the relative ETX improvement reaches a fixed threshold."""

    def __init__(self, relative_threshold: float):
        super().__init__()
        if not 0 <= relative_threshold < 1:
            raise ValueError("relative_threshold must be in [0, 1)")
        self.relative_threshold = relative_threshold

    def threshold(self) -> float:
        return self.relative_threshold

    def _accept_candidate(self, current_cost: float, candidate_cost: float) -> bool:
        relative_improvement = (current_cost - candidate_cost) / current_cost
        return relative_improvement >= self.relative_threshold


class VolatilityAwareEtxSelector(FixedThresholdEtxSelector):
    """Adapt hysteresis using an EWMA of relative ETX changes across active links."""

    def __init__(self, settings: VolatilitySettings):
        super().__init__(settings.minimum_threshold)
        self.settings = settings
        self.volatility = LinkQualityVolatility(settings.ewma_alpha)

    def observe(self, links: Iterable[dict[str, Any]]) -> float:
        return self.volatility.observe(links)

    def threshold(self) -> float:
        fraction = min(1.0, self.volatility.value / self.settings.volatility_scale)
        return self.settings.minimum_threshold + fraction * (
            self.settings.maximum_threshold - self.settings.minimum_threshold
        )

    def _accept_candidate(self, current_cost: float, candidate_cost: float) -> bool:
        relative_improvement = (current_cost - candidate_cost) / current_cost
        return relative_improvement >= self.threshold()


def _clamp_probability(value: float) -> float:
    return min(0.99, max(0.05, value))


def generate_quality_trace(
    topology: Topology,
    scenario: str,
    seed: int,
    rounds: int = DEFAULT_ROUNDS,
) -> tuple[list[list[dict[str, Any]]], list[dict[str, Any]]]:
    """Create one seeded trace and event list shared by every route-selection strategy."""
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario}")
    if rounds < 2:
        raise ValueError("rounds must be at least 2")
    rng = random.Random(seed)
    original = deepcopy(topology.links)
    trace: list[list[dict[str, Any]]] = []
    events: list[dict[str, Any]] = []
    target_edge = frozenset(("A", "B"))
    failure_edge = frozenset(("E", "F"))
    failure_start = rounds * 3 // 8
    recovery_start = rounds * 5 // 8

    for step in range(rounds):
        sample = deepcopy(original)
        for link in sample:
            edge = frozenset((link["u"], link["v"]))
            probability: float | None = None
            if edge == target_edge:
                if scenario == "Low variability":
                    probability = 0.712 + rng.uniform(-0.004, 0.004)
                elif scenario == "High variability":
                    probability = 0.72 + rng.uniform(-0.07, 0.07)
                elif scenario == "Gradual deterioration":
                    fraction = min(1.0, step / max(1, rounds // 2))
                    probability = 0.80 - fraction * 0.36 + rng.uniform(-0.002, 0.002)
                elif scenario == "Sudden severe deterioration":
                    probability = 0.80 if step < rounds // 3 else (
                        0.30 if step < 2 * rounds // 3 else 0.80
                    )
                elif scenario == "Failure and recovery":
                    probability = 0.55
            if probability is not None:
                probability = _clamp_probability(probability)
                link["forward"] = probability
                link["reverse"] = probability
            if scenario == "Failure and recovery" and edge == failure_edge:
                if step == failure_start:
                    events.append({
                        "round": step,
                        "event": "failure",
                        "u": "E",
                        "v": "F",
                    })
                if step == recovery_start:
                    events.append({
                        "round": step,
                        "event": "recovery",
                        "u": "E",
                        "v": "F",
                    })
                link["available"] = step < failure_start or step >= recovery_start
        trace.append(sample)
    return trace, events


def _make_selectors(settings: VolatilitySettings) -> dict[str, RouteSelector]:
    return {
        "Standard ETX": StandardEtxSelector(),
        "Fixed-threshold ETX": FixedThresholdEtxSelector(settings.fixed_threshold),
        "Volatility-aware ETX": VolatilityAwareEtxSelector(settings),
    }


def _event_responses(
    events: list[dict[str, Any]],
    selectors: dict[str, RouteSelector],
    event_state: dict[str, dict[str, Any]],
    step: int,
) -> None:
    for event in events:
        if event["round"] != step:
            continue
        key = event["event"]
        edge = frozenset((event["u"], event["v"]))
        for name, selector in selectors.items():
            state = event_state[name]
            if key == "failure":
                state["failed_edge"] = edge
                state["pre_failure_path"] = list(selector.path) if selector.path else None
            else:
                state["recovery_round"] = step
                state["recovery_target"] = state.get("pre_failure_path")


def _run_trial(
    base_topology: Topology,
    config: dict[str, Any],
    scenario: str,
    seed: int,
    rounds: int,
    settings: VolatilitySettings,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    trace, events = generate_quality_trace(base_topology, scenario, seed, rounds)
    topology = Topology(base_topology.nodes, deepcopy(trace[0]))
    protocol = LinkState(topology, "etx")
    source = config["source"]
    destination = config["destination"]
    selectors = _make_selectors(settings)
    event_state = {
        name: {
            "failure_response_rounds": None,
            "recovery_response_rounds": None,
            "pre_failure_path": None,
        }
        for name in selectors
    }
    link_state_messages = 0
    timeline: list[dict[str, Any]] = []
    rows_by_strategy: dict[str, list[dict[str, Any]]] = {name: [] for name in selectors}

    for step, sample in enumerate(trace):
        for current, updated in zip(topology.links, sample):
            current.update(updated)
        result = protocol.run()
        link_state_messages += result.messages
        candidate = protocol.path(source, destination)
        _event_responses(events, selectors, event_state, step)
        for name, selector in selectors.items():
            if isinstance(selector, VolatilityAwareEtxSelector):
                selector.observe(topology.links)
            selected = selector.select(candidate, topology)
            selected_cost = (
                path_etx(selected, topology.links) if selected is not None else math.inf
            )
            state = event_state[name]
            failed_edge = state.get("failed_edge")
            if (
                failed_edge is not None
                and state["failure_response_rounds"] is None
                and selected is not None
                and all(
                    frozenset((start, end)) != failed_edge
                    for start, end in zip(selected, selected[1:])
                )
            ):
                failure_round = next(
                    event["round"] for event in events if event["event"] == "failure"
                )
                state["failure_response_rounds"] = step - failure_round
            recovery_round = state.get("recovery_round")
            recovery_target = state.get("recovery_target")
            if (
                recovery_round is not None
                and state["recovery_response_rounds"] is None
                and recovery_target is not None
                and selected == recovery_target
            ):
                state["recovery_response_rounds"] = step - recovery_round
            row = {
                "scenario": scenario,
                "seed": seed,
                "round": step,
                "strategy": name,
                "candidate_route": "->".join(candidate) if candidate else "UNREACHABLE",
                "selected_route": "->".join(selected) if selected else "UNREACHABLE",
                "selected_etx": selected_cost if math.isfinite(selected_cost) else None,
                "volatility": (
                    selector.volatility.value
                    if isinstance(selector, VolatilityAwareEtxSelector)
                    else 0.0
                ),
                "switch_threshold": selector.threshold(),
                "link_state_messages_this_round": result.messages,
            }
            rows_by_strategy[name].append(row)
            timeline.append(row)

    trial_rows = []
    for name, selector in selectors.items():
        rows = rows_by_strategy[name]
        finite_etx = [row["selected_etx"] for row in rows if row["selected_etx"] is not None]
        state = event_state[name]
        trial_rows.append({
            "scenario": scenario,
            "seed": seed,
            "strategy": name,
            "route_switches": selector.switches,
            "average_selected_etx": statistics.fmean(finite_etx) if finite_etx else None,
            "cumulative_selected_etx": math.fsum(finite_etx),
            "unavailable_route_rounds": rounds - len(finite_etx),
            "failure_response_rounds": state["failure_response_rounds"],
            "recovery_response_rounds": state["recovery_response_rounds"],
            "link_state_control_messages": link_state_messages,
        })
    return trial_rows, timeline


def _aggregate(trial_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics = (
        "route_switches",
        "average_selected_etx",
        "cumulative_selected_etx",
        "unavailable_route_rounds",
        "failure_response_rounds",
        "recovery_response_rounds",
        "link_state_control_messages",
    )
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in trial_rows:
        grouped.setdefault((row["scenario"], row["strategy"]), []).append(row)
    result = []
    for (scenario, strategy), rows in grouped.items():
        summary: dict[str, Any] = {
            "scenario": scenario,
            "strategy": strategy,
            "trials": len(rows),
        }
        for metric in metrics:
            values = [row[metric] for row in rows if row[metric] is not None]
            summary[f"{metric}_mean"] = statistics.fmean(values) if values else None
            summary[f"{metric}_stdev"] = statistics.stdev(values) if len(values) > 1 else 0.0
        result.append(summary)
    return result


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write an empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _plot_results(
    aggregate: list[dict[str, Any]],
    timeline: list[dict[str, Any]],
    output: Path,
) -> None:
    colors = ("#4472C4", "#ED7D31", "#70AD47")
    scenario_labels = list(SCENARIOS)
    strategy_labels = list(STRATEGIES)
    width = 0.24

    fig, axis = plt.subplots(figsize=(12, 5))
    for index, strategy in enumerate(strategy_labels):
        rows = [
            next(row for row in aggregate if row["scenario"] == scenario and row["strategy"] == strategy)
            for scenario in scenario_labels
        ]
        x = [position + (index - 1) * width for position in range(len(scenario_labels))]
        axis.bar(
            x,
            [row["route_switches_mean"] for row in rows],
            width,
            yerr=[row["route_switches_stdev"] for row in rows],
            label=strategy,
            color=colors[index],
            capsize=3,
        )
    axis.set_xticks(range(len(scenario_labels)), scenario_labels, rotation=18, ha="right")
    axis.set(title="Route changes across dynamic link-quality trials", ylabel="Mean route switches")
    axis.legend()
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output / "route_switches.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for axis, mean_key, deviation_key, title, ylabel in (
        (
            axes[0],
            "average_selected_etx_mean",
            "average_selected_etx_stdev",
            "Average selected-route ETX",
            "ETX per reachable round",
        ),
        (
            axes[1],
            "cumulative_selected_etx_mean",
            "cumulative_selected_etx_stdev",
            "Cumulative selected-route ETX",
            "Sum of ETX across reachable rounds",
        ),
    ):
        for index, strategy in enumerate(strategy_labels):
            rows = [
                next(row for row in aggregate if row["scenario"] == scenario and row["strategy"] == strategy)
                for scenario in scenario_labels
            ]
            x = [position + (index - 1) * width for position in range(len(scenario_labels))]
            axis.bar(
                x,
                [row[mean_key] for row in rows],
                width,
                yerr=[row[deviation_key] for row in rows],
                label=strategy,
                color=colors[index],
                capsize=3,
            )
        axis.set_xticks(range(len(scenario_labels)), scenario_labels, rotation=22, ha="right")
        axis.set(title=title, ylabel=ylabel)
        axis.grid(axis="y", alpha=0.25)
    axes[0].legend()
    fig.tight_layout()
    fig.savefig(output / "path_etx.png", dpi=160)
    plt.close(fig)

    selected_timeline = [row for row in timeline if row["scenario"] == "High variability"]
    route_names = sorted({row["selected_route"] for row in selected_timeline})
    route_numbers = {name: index for index, name in enumerate(route_names)}
    fig, axis = plt.subplots(figsize=(12, 5))
    for index, strategy in enumerate(strategy_labels):
        rows = sorted(
            (row for row in selected_timeline if row["strategy"] == strategy),
            key=lambda row: row["round"],
        )
        axis.step(
            [row["round"] for row in rows],
            [route_numbers[row["selected_route"]] + (index - 1) * 0.08 for row in rows],
            where="post",
            label=strategy,
            color=colors[index],
        )
    axis.set_yticks(range(len(route_names)), route_names)
    axis.set(
        title="Selected route over one recorded high-variability trial",
        xlabel="Simulation round",
        ylabel="Selected source-to-destination route",
    )
    axis.legend()
    axis.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output / "route_timeline.png", dpi=160)
    plt.close(fig)

    failure_rows = [
        row for row in aggregate
        if row["scenario"] == "Failure and recovery"
    ]
    fig, axis = plt.subplots(figsize=(8, 5))
    x = list(range(len(strategy_labels)))
    response_width = 0.35
    for offset, event in enumerate(("failure", "recovery")):
        key = f"{event}_response_rounds"
        ordered = [
            next(row for row in failure_rows if row["strategy"] == strategy)
            for strategy in strategy_labels
        ]
        means = [row[f"{key}_mean"] for row in ordered]
        axis.bar(
            [position + (offset - 0.5) * response_width for position in x],
            [value if value is not None else math.nan for value in means],
            response_width,
            yerr=[
                row[f"{key}_stdev"] if value is not None else math.nan
                for row, value in zip(ordered, means)
            ],
            label=f"{event.title()} response",
            color=("#C0504D", "#70AD47")[offset],
            capsize=3,
        )
    axis.set_xticks(x, strategy_labels, rotation=10, ha="right")
    axis.set(
        title="Response after complete link failure and recovery",
        ylabel="Rounds from event to usable/returned route",
    )
    axis.legend()
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output / "failure_recovery_response.png", dpi=160)
    plt.close(fig)


def run_volatility_experiment(
    topology: Topology,
    config: dict[str, Any],
    output_dir: str | Path,
    *,
    trials: int = DEFAULT_TRIALS,
    seed: int = DEFAULT_SEED,
    rounds: int = DEFAULT_ROUNDS,
    settings: VolatilitySettings | None = None,
) -> dict[str, Any]:
    """Run paired seeded trials and save raw measurements, aggregates, and graphs."""
    if trials < 1:
        raise ValueError("trials must be at least 1")
    if rounds < 2:
        raise ValueError("rounds must be at least 2")
    active_settings = settings or VolatilitySettings()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    trial_rows: list[dict[str, Any]] = []
    timeline: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        for trial in range(trials):
            trial_seed = seed + trial
            current_rows, current_timeline = _run_trial(
                topology,
                config,
                scenario,
                trial_seed,
                rounds,
                active_settings,
            )
            trial_rows.extend(current_rows)
            if trial_seed == DEFAULT_SEED:
                timeline.extend(current_timeline)
    aggregate = _aggregate(trial_rows)
    _write_csv(output / "trials.csv", trial_rows)
    _write_csv(output / "aggregate.csv", aggregate)
    if not timeline:
        _, timeline = _run_trial(
            topology,
            config,
            "High variability",
            seed,
            rounds,
            active_settings,
        )
    _write_csv(output / "route_timeline.csv", timeline)
    _plot_results(aggregate, timeline, output)
    return {
        "trials": trial_rows,
        "aggregate": aggregate,
        "timeline": timeline,
        "output_dir": output,
        "settings": active_settings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    parser.add_argument("--fixed-threshold", type=float, default=0.10)
    parser.add_argument("--minimum-threshold", type=float, default=0.02)
    parser.add_argument("--maximum-threshold", type=float, default=0.45)
    parser.add_argument("--ewma-alpha", type=float, default=0.30)
    parser.add_argument("--volatility-scale", type=float, default=0.08)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "results" / "volatility",
    )
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parent
    topology, config = Topology.from_json(root / "config.json")
    settings = VolatilitySettings(
        fixed_threshold=arguments.fixed_threshold,
        minimum_threshold=arguments.minimum_threshold,
        maximum_threshold=arguments.maximum_threshold,
        ewma_alpha=arguments.ewma_alpha,
        volatility_scale=arguments.volatility_scale,
    )
    result = run_volatility_experiment(
        topology,
        config,
        arguments.output,
        trials=arguments.trials,
        seed=arguments.seed,
        rounds=arguments.rounds,
        settings=settings,
    )
    print(f"Trials per scenario: {arguments.trials}; rounds per trial: {arguments.rounds}")
    print(f"Seed range: {arguments.seed}..{arguments.seed + arguments.trials - 1}")
    print("\nMean +/- standard deviation across trials")
    for row in result["aggregate"]:
        print(
            f'{row["scenario"]:30} {row["strategy"]:24} '
            f'switches={row["route_switches_mean"]:.2f} +/- {row["route_switches_stdev"]:.2f} '
            f'avg_ETX={row["average_selected_etx_mean"]:.4f} '
            f'cum_ETX={row["cumulative_selected_etx_mean"]:.2f} '
            f'unavailable={row["unavailable_route_rounds_mean"]:.2f}'
        )
    print(f"\nMeasurements and graphs: {result['output_dir']}")


if __name__ == "__main__":
    main()
