"""Cost functions used by the routing protocols."""

from __future__ import annotations

import math
from typing import Iterable, Mapping


def etx(forward: float, reverse: float) -> float:
    """Return ETX = 1/(df*dr), rejecting invalid delivery probabilities."""
    for name, probability in (("forward", forward), ("reverse", reverse)):
        if not math.isfinite(probability) or not 0 < probability <= 1:
            raise ValueError(f"{name} delivery probability must be in (0, 1]")
    return 1.0 / (forward * reverse)


def link_cost(link: Mapping[str, object], metric: str) -> float:
    """Return an available link's cost, or infinity if the link is unavailable."""
    if not bool(link["available"]):
        return math.inf
    if metric == "hop":
        return 1.0
    if metric == "etx":
        return etx(float(link["forward"]), float(link["reverse"]))
    raise ValueError(f"Unknown routing metric: {metric}")


def path_etx(path: Iterable[str], links: Iterable[Mapping[str, object]]) -> float:
    """Sum ETX values along a path; return infinity if an edge is unavailable."""
    path_nodes = list(path)
    if len(path_nodes) < 2:
        return 0.0
    by_edge = {
        frozenset((str(link["u"]), str(link["v"]))): link
        for link in links
    }
    total = 0.0
    for start, end in zip(path_nodes, path_nodes[1:]):
        link = by_edge.get(frozenset((start, end)))
        if link is None or not bool(link["available"]):
            return math.inf
        total += etx(float(link["forward"]), float(link["reverse"]))
    return total
