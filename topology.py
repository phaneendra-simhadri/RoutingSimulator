"""Network topology loading and graph construction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

from metrics import link_cost


class Topology:
    def __init__(self, nodes: list[str], links: list[dict[str, Any]]):
        if len(nodes) != len(set(nodes)) or not nodes:
            raise ValueError("Topology nodes must be non-empty and unique")
        self.nodes = list(nodes)
        self.links = [dict(link) for link in links]
        known_nodes = set(nodes)
        seen_edges: set[frozenset[str]] = set()
        for link in self.links:
            if link["u"] not in known_nodes or link["v"] not in known_nodes:
                raise ValueError(f"Unknown endpoint in link {link}")
            edge = frozenset((link["u"], link["v"]))
            if len(edge) != 2 or edge in seen_edges:
                raise ValueError(f"Invalid or duplicate link {link}")
            seen_edges.add(edge)
            link["forward"] = float(link["forward"])
            link["reverse"] = float(link["reverse"])
            link["available"] = bool(link["available"])
            # Validate probability values even while a link is down.
            link_cost({**link, "available": True}, "etx")

    @classmethod
    def from_json(cls, path: str | Path) -> tuple["Topology", dict[str, Any]]:
        with Path(path).open(encoding="utf-8") as file:
            config = json.load(file)
        return cls(config["nodes"], config["links"]), config

    def graph(self, metric: str = "hop", include_unavailable: bool = False) -> nx.Graph:
        graph = nx.Graph()
        graph.add_nodes_from(self.nodes)
        for link in self.links:
            if not link["available"] and not include_unavailable:
                continue
            graph.add_edge(
                link["u"],
                link["v"],
                cost=link_cost(link, metric),
                available=link["available"],
                forward=link["forward"],
                reverse=link["reverse"],
            )
        return graph

    def set_link_available(self, u: str, v: str, available: bool) -> None:
        for link in self.links:
            if {link["u"], link["v"]} == {u, v}:
                link["available"] = available
                return
        raise KeyError(f"No link exists between {u} and {v}")

    def link(self, u: str, v: str) -> dict[str, Any]:
        for link in self.links:
            if {link["u"], link["v"]} == {u, v}:
                return link
        raise KeyError(f"No link exists between {u} and {v}")
