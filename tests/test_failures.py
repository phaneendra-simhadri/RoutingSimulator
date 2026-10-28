import math

import pytest

from distance_vector import DistanceVector
from link_state import LinkState
from topology import Topology


@pytest.mark.parametrize("protocol_type", [DistanceVector, LinkState])
def test_route_around_failure_and_recover(protocol_type):
    topology = Topology(
        ["A", "B", "C", "D"],
        [
            {"u": "A", "v": "B", "forward": 1, "reverse": 1, "available": True},
            {"u": "B", "v": "D", "forward": 1, "reverse": 1, "available": True},
            {"u": "A", "v": "C", "forward": 1, "reverse": 1, "available": True},
            {"u": "C", "v": "D", "forward": 1, "reverse": 1, "available": True},
        ],
    )
    protocol = protocol_type(topology, "hop", **({"poison_reverse": True} if protocol_type is DistanceVector else {}))
    initial = protocol.run()
    initial_path = protocol.path("A", "D")
    assert initial.converged and initial_path is not None
    topology.set_link_available("A", "B", False)
    failure = protocol.run()
    assert failure.converged
    assert protocol.path("A", "D") == ["A", "C", "D"]
    topology.set_link_available("A", "B", True)
    recovery = protocol.run()
    assert recovery.converged
    assert protocol.path("A", "D") == initial_path


def test_destination_becomes_unreachable_when_all_routes_fail():
    topology = Topology(
        ["A", "B"],
        [{"u": "A", "v": "B", "forward": 1, "reverse": 1, "available": True}],
    )
    protocol = DistanceVector(topology, "hop", poison_reverse=True)
    protocol.run()
    topology.set_link_available("A", "B", False)
    result = protocol.run()
    assert result.converged
    assert math.isinf(protocol.tables["A"]["B"].cost)
