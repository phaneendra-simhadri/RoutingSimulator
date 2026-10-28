"""Helpers for reporting measured routes and costs."""

from __future__ import annotations

import math
from typing import Any

from metrics import path_etx
from topology import Topology


def describe_path(path: list[str] | None, topology: Topology) -> dict[str, Any]:
    if path is None:
        return {"path": None, "hop_count": None, "etx": math.inf}
    return {
        "path": path,
        "hop_count": max(0, len(path) - 1),
        "etx": path_etx(path, topology.links),
    }


def path_cost(path: list[str] | None, topology: Topology, metric: str) -> float:
    if path is None:
        return math.inf
    if metric == "hop":
        return float(len(path) - 1)
    if metric == "etx":
        return path_etx(path, topology.links)
    raise ValueError(f"Unknown routing metric: {metric}")
