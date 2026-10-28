"""Synchronous Distance Vector routing using neighbor advertisements."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

from metrics import link_cost
from topology import Topology


@dataclass(frozen=True)
class Route:
    cost: float
    next_hop: str | None


@dataclass
class RoutingResult:
    tables: dict[str, dict[str, Route]]
    rounds: int
    messages: int
    converged: bool
    changes: list[dict[str, object]]


class DistanceVector:
    def __init__(
        self,
        topology: Topology,
        metric: str,
        *,
        split_horizon: bool = False,
        poison_reverse: bool = False,
        maximum_hop_metric: int = 16,
        maximum_rounds: int = 100,
    ):
        self.topology = topology
        self.metric = metric
        self.split_horizon = split_horizon
        self.poison_reverse = poison_reverse
        self.maximum_hop_metric = maximum_hop_metric
        self.maximum_rounds = maximum_rounds
        self.tables = self._initial_tables()

    def _initial_tables(self) -> dict[str, dict[str, Route]]:
        tables = {
            node: {dest: Route(math.inf, None) for dest in self.topology.nodes}
            for node in self.topology.nodes
        }
        for node in self.topology.nodes:
            tables[node][node] = Route(0.0, None)
        for link in self.topology.links:
            if link["available"]:
                cost = link_cost(link, self.metric)
                tables[link["u"]][link["v"]] = Route(cost, link["v"])
                tables[link["v"]][link["u"]] = Route(cost, link["u"])
        return tables

    def _edge_cost(self, u: str, v: str) -> float:
        try:
            return link_cost(self.topology.link(u, v), self.metric)
        except KeyError:
            return math.inf

    def _advertised_cost(self, sender: str, receiver: str, destination: str) -> float | None:
        route = self.tables[sender][destination]
        if (
            self.split_horizon
            and route.next_hop == receiver
            and not self.poison_reverse
        ):
            return None
        if self.poison_reverse and route.next_hop == receiver:
            return math.inf
        return route.cost

    def run(self) -> RoutingResult:
        messages = 0
        changes: list[dict[str, object]] = []
        converged = False
        rounds = 0
        for round_number in range(1, self.maximum_rounds + 1):
            old = self.tables
            new: dict[str, dict[str, Route]] = {}
            for node in self.topology.nodes:
                table = {dest: Route(math.inf, None) for dest in self.topology.nodes}
                table[node] = Route(0.0, None)
                for neighbor in self.topology.nodes:
                    edge = self._edge_cost(node, neighbor)
                    if not math.isfinite(edge):
                        continue
                    messages += 1
                    for destination in self.topology.nodes:
                        advertised = self._advertised_cost(neighbor, node, destination)
                        if advertised is None or not math.isfinite(advertised):
                            continue
                        candidate = edge + advertised
                        if self.metric == "hop" and candidate >= self.maximum_hop_metric:
                            continue
                        current = table[destination]
                        if candidate < current.cost or (
                            candidate == current.cost
                            and current.next_hop is not None
                            and neighbor < current.next_hop
                        ):
                            table[destination] = Route(candidate, neighbor)
                new[node] = table
            changed = [
                (node, dest, old[node][dest], new[node][dest])
                for node in self.topology.nodes
                for dest in self.topology.nodes
                if old[node][dest] != new[node][dest]
            ]
            self.tables = new
            rounds = round_number
            for node, destination, before, after in changed:
                changes.append({
                    "round": round_number,
                    "node": node,
                    "destination": destination,
                    "cost": after.cost,
                    "next_hop": after.next_hop,
                })
            if not changed:
                converged = True
                break
        return RoutingResult(self.tables, rounds, messages, converged, changes)

    def path(self, source: str, destination: str) -> list[str] | None:
        if source not in self.tables or destination not in self.tables[source]:
            raise KeyError("Source or destination is not in the topology")
        if not math.isfinite(self.tables[source][destination].cost):
            return None
        path = [source]
        current = source
        while current != destination:
            next_hop = self.tables[current][destination].next_hop
            if next_hop is None or next_hop in path:
                return None
            if not math.isfinite(self._edge_cost(current, next_hop)):
                return None
            path.append(next_hop)
            current = next_hop
        return path
