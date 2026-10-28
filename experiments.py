"""Reproducible routing scenarios and generated result artifacts."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

from distance_vector import DistanceVector
from link_state import LinkState
from simulator import describe_path, path_cost
from topology import Topology


ALGORITHMS = ("Distance Vector", "Link State")
METRICS = ("hop", "etx")


def _new_protocol(algorithm: str, topology: Topology, metric: str, config: dict[str, Any]):
    if algorithm == "Distance Vector":
        settings = config["distance_vector"]
        return DistanceVector(
            topology,
            metric,
            split_horizon=settings["split_horizon"],
            poison_reverse=settings["poison_reverse"],
            maximum_hop_metric=settings["maximum_hop_metric"],
            maximum_rounds=settings["maximum_rounds"],
        )
    return LinkState(topology, metric)


def _route(protocol: Any, source: str, destination: str) -> list[str] | None:
    return protocol.path(source, destination)


def _measure(protocol: Any, source: str, destination: str, topology: Topology) -> dict[str, Any]:
    path = _route(protocol, source, destination)
    return describe_path(path, topology)


def _summary_row(
    algorithm: str,
    metric: str,
    stage: str,
    measured: dict[str, Any],
    rounds: int,
    messages: int,
    topology: Topology,
) -> dict[str, Any]:
    return {
        "algorithm": algorithm,
        "metric": metric,
        "stage": stage,
        "path": "->".join(measured["path"]) if measured["path"] else "UNREACHABLE",
        "hop_count": measured["hop_count"],
        "path_etx": (
            f'{measured["etx"]:.6f}' if math.isfinite(measured["etx"]) else "inf"
        ),
        "selected_metric_cost": (
            f'{path_cost(measured["path"], topology, metric):.6f}'
            if measured["path"]
            else "inf"
        ),
        "convergence_rounds": rounds,
        "control_messages": messages,
        "reachable": measured["path"] is not None,
    }


def _render_graphs(
    topology: Topology,
    records: list[dict[str, Any]],
    output_dir: Path,
    source: str,
    destination: str,
    failure: tuple[str, str],
) -> None:
    failure_rows = [
        row for row in records
        if row["stage"] == "failure"
    ]
    initial_rows = [row for row in records if row["stage"] == "initial"]
    labels = [f'{row["algorithm"]}\n{row["metric"].upper()}' for row in failure_rows]

    fig, axis = plt.subplots(figsize=(9, 5))
    axis.bar(labels, [row["convergence_rounds"] for row in failure_rows], color="#4472C4")
    axis.set(title="Convergence after link failure", ylabel="Synchronous rounds")
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "convergence.png", dpi=160)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(10, 5))
    positions = list(range(len(failure_rows)))
    width = 0.25
    for offset, stage in enumerate(("initial", "failure", "recovery")):
        rows = [row for row in records if row["stage"] == stage]
        ordered = sorted(
            rows,
            key=lambda row: (
                ALGORITHMS.index(row["algorithm"]),
                METRICS.index(row["metric"]),
            ),
        )
        axis.bar(
            [position + (offset - 1) * width for position in positions],
            [row["control_messages"] for row in ordered],
            width,
            label=f"{stage.title()} discovery/recovery",
        )
    axis.set_xticks(positions, labels)
    axis.set(title="Routing control-message overhead", ylabel="Simulated message transmissions")
    axis.legend()
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "message_overhead.png", dpi=160)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(9, 5))
    hop_rows = [row for row in initial_rows if row["metric"] == "hop"]
    etx_rows = [row for row in initial_rows if row["metric"] == "etx"]
    positions = list(range(len(ALGORITHMS)))
    axis.bar(
        [position - 0.18 for position in positions],
        [float(row["path_etx"]) for row in sorted(hop_rows, key=lambda row: ALGORITHMS.index(row["algorithm"]))],
        width=0.36,
        label="Hop-count-selected route",
    )
    axis.bar(
        [position + 0.18 for position in positions],
        [float(row["path_etx"]) for row in sorted(etx_rows, key=lambda row: ALGORITHMS.index(row["algorithm"]))],
        width=0.36,
        label="ETX-selected route",
    )
    axis.set_xticks(positions, ALGORITHMS)
    axis.set(title=f"Route quality for {source} to {destination}", ylabel="Total path ETX")
    axis.legend()
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "path_quality.png", dpi=160)
    plt.close(fig)

    graph = nx.Graph()
    graph.add_nodes_from(topology.nodes)
    graph.add_edges_from((link["u"], link["v"]) for link in topology.links)
    positions_map = nx.spring_layout(graph, seed=23)
    fig, axis = plt.subplots(figsize=(8, 6))
    available_edges = [
        (link["u"], link["v"]) for link in topology.links
        if link["available"] and {link["u"], link["v"]} != set(failure)
    ]
    nx.draw_networkx_nodes(graph, positions_map, node_size=1000, node_color="#CFE2F3", ax=axis)
    nx.draw_networkx_labels(graph, positions_map, font_weight="bold", ax=axis)
    nx.draw_networkx_edges(graph, positions_map, edgelist=available_edges, width=2, ax=axis)
    nx.draw_networkx_edges(
        graph, positions_map, edgelist=[failure], style="dashed", edge_color="red", width=2, ax=axis
    )
    hop_path = next(row["path"] for row in initial_rows if row["algorithm"] == "Link State" and row["metric"] == "hop")
    if hop_path != "UNREACHABLE":
        route_edges = list(zip(hop_path.split("->"), hop_path.split("->")[1:]))
        nx.draw_networkx_edges(
            graph, positions_map, edgelist=route_edges, edge_color="#2E8B57", width=4, ax=axis
        )
    labels_map = {
        frozenset((link["u"], link["v"])): f'{link["forward"]:.2f}/{link["reverse"]:.2f}'
        for link in topology.links
    }
    nx.draw_networkx_edge_labels(
        graph, positions_map,
        edge_labels={(u, v): labels_map[frozenset((u, v))] for u, v in graph.edges},
        font_size=8, ax=axis,
    )
    axis.set_title("Configured topology: delivery probabilities; green = hop route, red dashed = failed then restored")
    axis.axis("off")
    fig.tight_layout()
    fig.savefig(output_dir / "topology.png", dpi=160)
    plt.close(fig)


def run_experiments(
    topology: Topology,
    config: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    source = config["source"]
    destination = config["destination"]
    failure = tuple(config["failure_link"])
    records: list[dict[str, Any]] = []
    initial_routes: dict[tuple[str, str], dict[str, Any]] = {}
    protocols: dict[tuple[str, str], Any] = {}
    phase_results: dict[str, dict[tuple[str, str], tuple[Any, Any]]] = {}

    for algorithm in ALGORITHMS:
        for metric in METRICS:
            protocol = _new_protocol(algorithm, topology, metric, config)
            result = protocol.run()
            measured = _measure(protocol, source, destination, topology)
            protocols[(algorithm, metric)] = protocol
            initial_routes[(algorithm, metric)] = measured
            phase_results.setdefault("initial", {})[(algorithm, metric)] = (result, measured)
            records.append(_summary_row(
                algorithm, metric, "initial", measured, result.rounds, result.messages, topology
            ))

    hop_route = initial_routes[("Link State", "hop")]["path"]
    etx_route = initial_routes[("Link State", "etx")]["path"]
    if hop_route is None or etx_route is None or hop_route == etx_route:
        raise RuntimeError("Configured lossy-link scenario did not produce different Hop and ETX paths")
    if path_cost(hop_route, topology, "etx") <= path_cost(etx_route, topology, "etx"):
        raise RuntimeError("Configured Hop route must have worse ETX than the ETX-selected route")

    topology.set_link_available(*failure, False)
    for algorithm in ALGORITHMS:
        for metric in METRICS:
            protocol = protocols[(algorithm, metric)]
            result = protocol.run()
            measured = _measure(protocol, source, destination, topology)
            phase_results.setdefault("failure", {})[(algorithm, metric)] = (result, measured)
            records.append(_summary_row(
                algorithm, metric, "failure", measured, result.rounds, result.messages, topology
            ))

    topology.set_link_available(*failure, True)
    for algorithm in ALGORITHMS:
        for metric in METRICS:
            protocol = protocols[(algorithm, metric)]
            result = protocol.run()
            measured = _measure(protocol, source, destination, topology)
            phase_results.setdefault("recovery", {})[(algorithm, metric)] = (result, measured)
            records.append(_summary_row(
                algorithm, metric, "recovery", measured, result.rounds, result.messages, topology
            ))

    for algorithm in ALGORITHMS:
        for metric in METRICS:
            failed = phase_results["failure"][(algorithm, metric)][1]["path"]
            recovered = phase_results["recovery"][(algorithm, metric)][1]["path"]
            if failed is None or recovered != initial_routes[(algorithm, metric)]["path"]:
                raise RuntimeError(f"{algorithm} + {metric} did not route around and recover from the link event")

    count_demo = run_count_to_infinity_demo()
    with (output / "summary.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    _render_graphs(topology, records, output, source, destination, failure)
    return {
        "records": records,
        "phase_results": phase_results,
        "count_to_infinity": count_demo,
        "source": source,
        "destination": destination,
        "failure": failure,
    }


def run_count_to_infinity_demo() -> dict[str, Any]:
    nodes = ["P", "Q", "R", "S"]
    links = [
        {"u": "P", "v": "Q", "forward": 1.0, "reverse": 1.0, "available": True},
        {"u": "Q", "v": "R", "forward": 1.0, "reverse": 1.0, "available": True},
        {"u": "R", "v": "S", "forward": 1.0, "reverse": 1.0, "available": True},
    ]
    outcomes: dict[str, Any] = {}
    for prevention in ("none", "split_horizon", "poison_reverse"):
        scenario_topology = Topology(nodes, links)
        settings = {
            "none": (False, False),
            "split_horizon": (True, False),
            "poison_reverse": (False, True),
        }[prevention]
        protocol = DistanceVector(
            scenario_topology,
            "hop",
            split_horizon=settings[0],
            poison_reverse=settings[1],
            maximum_hop_metric=16,
            maximum_rounds=40,
        )
        protocol.run()
        scenario_topology.set_link_available("R", "S", False)
        result = protocol.run()
        series = [
            change for change in result.changes
            if change["destination"] == "S" and change["node"] in ("Q", "R")
        ]
        outcomes[prevention] = {
            "rounds": result.rounds,
            "messages": result.messages,
            "converged": result.converged,
            "changes": series,
            "q_cost": protocol.tables["Q"]["S"].cost,
            "r_cost": protocol.tables["R"]["S"].cost,
            "reachable": protocol.path("P", "S") is not None,
        }
    return outcomes
