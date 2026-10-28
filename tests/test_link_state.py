import math

from link_state import LinkState
from topology import Topology


def test_dijkstra_finds_shortest_route_on_small_graph():
    topology = Topology(
        ["A", "B", "C", "D"],
        [
            {"u": "A", "v": "B", "forward": 1, "reverse": 1, "available": True},
            {"u": "B", "v": "D", "forward": 1, "reverse": 1, "available": True},
            {"u": "A", "v": "C", "forward": 1, "reverse": 1, "available": True},
            {"u": "C", "v": "D", "forward": 1, "reverse": 1, "available": True},
        ],
    )
    protocol = LinkState(topology, "hop")
    result = protocol.run()
    assert result.converged
    assert protocol.path("A", "D") in (["A", "B", "D"], ["A", "C", "D"])
    assert result.messages > 0


def test_link_state_excludes_failed_link_and_reports_unreachable():
    topology = Topology(
        ["A", "B", "C"],
        [
            {"u": "A", "v": "B", "forward": 1, "reverse": 1, "available": True},
            {"u": "B", "v": "C", "forward": 1, "reverse": 1, "available": True},
        ],
    )
    protocol = LinkState(topology, "hop")
    protocol.run()
    topology.set_link_available("B", "C", False)
    result = protocol.run()
    assert result.converged
    assert protocol.path("A", "C") is None
    assert math.isinf(result.tables["A"]["C"].cost)


def test_link_state_flooding_counts_link_transmissions():
    topology = Topology(
        ["A", "B"],
        [{"u": "A", "v": "B", "forward": 1, "reverse": 1, "available": True}],
    )
    result = LinkState(topology, "hop").run()
    # Each endpoint originates an LSA; the neighbor forwards it back once.
    assert result.messages == 4
    assert result.rounds == 2
