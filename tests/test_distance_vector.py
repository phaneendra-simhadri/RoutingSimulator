import math

from distance_vector import DistanceVector
from topology import Topology


def small_topology():
    return Topology(
        ["A", "B", "C", "D"],
        [
            {"u": "A", "v": "B", "forward": 1, "reverse": 1, "available": True},
            {"u": "B", "v": "D", "forward": 1, "reverse": 1, "available": True},
            {"u": "A", "v": "C", "forward": 1, "reverse": 1, "available": True},
            {"u": "C", "v": "D", "forward": 1, "reverse": 1, "available": True},
        ],
    )


def test_distance_vector_finds_minimum_cost_route_and_converges():
    protocol = DistanceVector(small_topology(), "hop", poison_reverse=True)
    result = protocol.run()
    assert result.converged
    assert protocol.tables["A"]["D"].cost == 2
    assert protocol.path("A", "D") in (["A", "B", "D"], ["A", "C", "D"])


def test_distance_vector_detects_unreachable_destinations():
    topology = small_topology()
    topology.set_link_available("B", "D", False)
    topology.set_link_available("C", "D", False)
    protocol = DistanceVector(topology, "hop", poison_reverse=True)
    protocol.run()
    assert math.isinf(protocol.tables["A"]["D"].cost)
    assert protocol.path("A", "D") is None


def test_control_message_count_is_one_vector_per_directed_link_per_round():
    topology = Topology(
        ["A", "B"],
        [{"u": "A", "v": "B", "forward": 1, "reverse": 1, "available": True}],
    )
    result = DistanceVector(topology, "hop").run()
    assert result.rounds == 1
    assert result.messages == 2


def test_poison_reverse_and_split_horizon_withdraw_failed_routes():
    for settings in ({"split_horizon": True}, {"poison_reverse": True}):
        topology = Topology(
            ["A", "B", "C"],
            [
                {"u": "A", "v": "B", "forward": 1, "reverse": 1, "available": True},
                {"u": "B", "v": "C", "forward": 1, "reverse": 1, "available": True},
            ],
        )
        protocol = DistanceVector(topology, "hop", **settings)
        protocol.run()
        topology.set_link_available("B", "C", False)
        result = protocol.run()
        assert result.converged
        assert math.isinf(protocol.tables["A"]["C"].cost)
