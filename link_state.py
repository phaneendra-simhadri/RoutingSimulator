"""Link State flooding and per-node Dijkstra route calculation."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Any

from distance_vector import Route
from metrics import link_cost
from topology import Topology


@dataclass
class LinkStateResult:
    tables: dict[str, dict[str, Route]]
    databases: dict[str, dict[str, dict[str, dict[str, Any]]]]
    rounds: int
    messages: int
    converged: bool


class LinkState:
    def __init__(self, topology: Topology, metric: str):
        self.topology = topology
        self.metric = metric
        self.databases: dict[str, dict[str, dict[str, dict[str, Any]]]] = {
            node: {} for node in topology.nodes
        }
        self._sequence = {node: 0 for node in topology.nodes}
        self._advertisements: dict[str, dict[str, dict[str, Any]]] = {}

    def _advertisement(self, origin: str) -> dict[str, dict[str, Any]]:
        return {
            link["v"] if link["u"] == origin else link["u"]: dict(link)
            for link in self.topology.links
            if link["available"] and origin in (link["u"], link["v"])
        }

    def _flood(self, changed_origins: list[str]) -> tuple[int, int]:
        pending: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
        # An origin's updated LSA is already known locally and is forwarded.
        for origin in changed_origins:
            for node in self.topology.nodes:
                if node != origin:
                    self.databases[node].pop(origin, None)
            self.databases[origin][origin] = self._advertisements[origin]
            pending[origin] = {origin: self._advertisements[origin]}
        messages = 0
        rounds = 0
        while any(pending.values()):
            rounds += 1
            next_pending: dict[str, dict[str, dict[str, dict[str, Any]]]] = {
                node: {} for node in self.topology.nodes
            }
            for sender, advertisements in pending.items():
                neighbors = self.topology.graph("hop").neighbors(sender)
                for destination in neighbors:
                    messages += len(advertisements)
                    for origin, advertisement in advertisements.items():
                        if origin not in self.databases[destination]:
                            self.databases[destination][origin] = advertisement
                            next_pending[destination][origin] = advertisement
            pending = next_pending
        return rounds, messages

    def run(self) -> LinkStateResult:
        changed: list[str] = []
        for node in self.topology.nodes:
            advertisement = self._advertisement(node)
            if self._advertisements.get(node) != advertisement:
                self._sequence[node] += 1
                self._advertisements[node] = advertisement
                changed.append(node)
        if changed:
            rounds, messages = self._flood(changed)
        else:
            rounds, messages = 0, 0
        tables = {node: self._dijkstra(node) for node in self.topology.nodes}
        return LinkStateResult(tables, self.databases, rounds, messages, True)

    def _dijkstra(self, source: str) -> dict[str, Route]:
        adjacency: dict[str, dict[str, float]] = {node: {} for node in self.topology.nodes}
        for u in self.topology.nodes:
            for v, link in self.databases[u].get(u, {}).items():
                reverse = self.databases[v].get(v, {}).get(u)
                if reverse is None:
                    continue
                # Both endpoint advertisements must agree the link is available.
                edge_weight = link_cost(link, self.metric)
                adjacency[u][v] = edge_weight
                adjacency[v][u] = edge_weight
        distances = {node: math.inf for node in self.topology.nodes}
        previous: dict[str, str] = {}
        distances[source] = 0.0
        queue: list[tuple[float, str]] = [(0.0, source)]
        while queue:
            distance, node = heapq.heappop(queue)
            if distance != distances[node]:
                continue
            for neighbor, weight in adjacency[node].items():
                candidate = distance + weight
                if candidate < distances[neighbor]:
                    distances[neighbor] = candidate
                    previous[neighbor] = node
                    heapq.heappush(queue, (candidate, neighbor))
        routes: dict[str, Route] = {}
        for destination, cost in distances.items():
            if destination == source or not math.isfinite(cost):
                routes[destination] = Route(cost, None)
                continue
            current = destination
            while previous.get(current) != source and current in previous:
                current = previous[current]
            routes[destination] = Route(cost, current if current in previous else None)
        return routes

    def path(self, source: str, destination: str) -> list[str] | None:
        if source not in self.topology.nodes or destination not in self.topology.nodes:
            raise KeyError("Source or destination is not in the topology")
        if not math.isfinite(self._dijkstra(source)[destination].cost):
            return None
        path = [source]
        current = source
        while current != destination:
            next_hop = self._dijkstra(current)[destination].next_hop
            if next_hop is None or next_hop in path:
                return None
            path.append(next_hop)
            current = next_hop
        return path
