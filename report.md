# Comparative Evaluation of Distance Vector and Link State Routing Using Hop-Count and ETX Metrics Under Link Failures

## 1. Abstract

This project implements and compares two routing approaches—Distance Vector using synchronous Bellman–Ford updates and Link State using controlled LSA flooding followed by per-node Dijkstra computation. Each is evaluated using Hop Count and Expected Transmission Count (ETX) on the same fixed eight-node network. The simulator executes initial discovery, a configured A-B link failure, and restoration; it records paths, route costs, synchronous convergence rounds, and simulated control-message transmissions. A separate four-node experiment demonstrates count to infinity and tests split horizon and poison reverse. In the measured A-to-D route, both algorithms select A-B-D under Hop Count (2 hops, ETX 4.540353) and A-E-F-D under ETX (3 hops, ETX 3.123698). These are simulation results for the supplied deterministic configuration, not real network performance measurements.

## 2. Introduction

Routing protocols select next hops so traffic can reach destinations across interconnected nodes. Distance Vector routers learn destination costs from neighboring routers. Link State routers distribute information about local links and calculate routes from a topology database. In either family, the route depends on the metric.

Hop Count treats all available links alike. That is easy to understand, but it does not reflect link quality. ETX estimates how many transmissions, including retransmissions, are expected to successfully deliver a packet over a link. The comparison is useful for wireless networks, where a physically available connection may be unreliable.

## 3. Problem Statement

The minimum-hop path can be less desirable when it contains a lossy link. Routing updates also need to react when links fail and recover. The project asks how the two implemented routing protocols and two metrics choose routes and how their simulated update overhead differs under one reproducible topology and event sequence.

## 4. Objectives

1. Implement explicit Bellman–Ford Distance Vector updates using only neighbor advertisements.
2. Implement controlled Link State flooding and an explicit Dijkstra algorithm at each simulated router.
3. Implement Hop Count and ETX consistently for both protocols.
4. Measure routes, convergence rounds, and control-message transmissions for initial, failure, and recovery stages.
5. Demonstrate count to infinity and observe split horizon and poison reverse on a small separate topology.
6. Validate calculations, failures, recovery, convergence, and reproducibility with automated tests.

## 5. Literature Review

De Couto et al. introduced ETX as a path metric for multi-hop wireless routing. Their work motivates accounting for retransmissions instead of selecting routes by hop count alone. This project uses the core ETX idea but does not reproduce the paper's complete wireless testbed, measurement process, or routing protocol.

RIP Version 2 (RFC 2453) describes a distance-vector routing protocol and finite hop metric. OSPF Version 2 (RFC 2328) specifies a link-state protocol with link-state advertisements and a shortest-path calculation. These standards provide protocol context; this implementation is a teaching simulator, not a conforming RIP or OSPF implementation.

Research on loop-free distance-vector routing, including Garcia-Luna-Aceves' work on diffusing computations, shows that preventing loops is a broader protocol-design problem than applying a single local heuristic. This simulator demonstrates only the effect of split horizon and poison reverse on its chosen topology.

## 6. Background and Related Work

### Distance Vector

For node `x` and destination `d`, Bellman–Ford considers neighboring nodes `v` and their advertised estimate `D_v(d)`:

`D_x(d) = min over neighbors v of [ cost(x,v) + D_v(d) ]`

The update is distributed: a node uses the prior-round information advertised by its neighbors. Without safeguards, stale information can cause a routing loop and successively larger estimates, known as count to infinity.

### Link State

Each router originates link-state information about its currently available adjacent links. Flooding distributes each new advertisement across the connected topology. Every router then runs its own shortest-path calculation over its locally collected database. Flooding is network-wide information distribution; Dijkstra is a local computation performed independently at each router.

### Metric distinction

The protocol decides how topology or route information is learned. The metric assigns costs to links and thereby influences shortest-path selection. Neither protocol is inherently tied to Hop Count or ETX.

## 7. Proposed Methodology

The experiment uses the deterministic topology in `config.json` with nodes A-H and ten undirected links. Each edge stores forward and reverse delivery probabilities and an availability flag. The selected route query is A to D; the configured failure disables A-B, after which A-B is restored.

All four combinations use the same nodes, probabilities, event, and source/destination. Protocol objects are retained between stages: initial tables/LS databases are updated after failure, then updated again after recovery. Initial discovery and incremental event overhead are reported separately.

The configuration also creates a distinct P-Q-R-S chain for the count-to-infinity exercise. R-S is withdrawn after initial routes have converged. The experiment is repeated with no prevention, split horizon, and poison reverse.

## 8. System Architecture

- `topology.py`: validates and loads JSON topology; builds NetworkX graph views.
- `metrics.py`: validates delivery probabilities and calculates edge/path ETX.
- `distance_vector.py`: synchronous neighbor vector exchange, convergence, next hops, and optional split horizon/poison reverse.
- `link_state.py`: per-origin advertisements, controlled flooding, per-node databases, and explicit Dijkstra route calculation.
- `simulator.py`: shared route and cost descriptions.
- `experiments.py`: event sequence, measurement rows, count-to-infinity exercise, CSV and chart generation.
- `main.py`: command-line entry point.
- `tests/`: focused correctness and repeatability checks.

NetworkX is used for topology storage, neighbor access, and visualization only. Neither shortest-path algorithm is delegated to NetworkX.

## 9. Routing Metrics

### Hop Count

Every available edge has cost 1. Path cost is the sum of its edge costs, which is exactly the number of hops. Unavailable links are omitted from route calculations.

### Expected Transmission Count

For a link with forward delivery probability `df` and reverse delivery probability `dr`:

`ETX = 1 / (df * dr)`

Path ETX is the sum of edge ETX values. Both directions matter because successful wireless delivery typically requires data to arrive forward and an acknowledgment to return. A poor return path can cause retransmissions even when forward delivery is good. This model assumes stable probabilities and independent attempts; it does not simulate individual transmissions.

Probabilities are validated to be finite and in `(0, 1]`, including for currently unavailable links. A path containing an unavailable or absent edge has infinite ETX.

## 10. Algorithm Design

### Distance Vector

Each node maintains a cost and next hop for every destination. At each synchronous round, every active directed neighbor relationship carries one complete vector. Nodes calculate new tables from the previous round's advertisements. The simulation ends when no table changes or the configured maximum number of rounds is reached. The Hop Count scenario uses a ceiling of 16 for the separate count-to-infinity experiment. Split horizon omits a route advertisement to its next hop; poison reverse advertises that route as infinity to that neighbor.

### Link State

Each node originates an LSA containing its available adjacent links. During each synchronous flooding step, nodes forward newly learned LSAs to active neighbors; an LSA already present in a database is not forwarded again by that node. Each router reconstructs its view from LSAs that are present at both link endpoints, then runs Dijkstra locally. On a failure or recovery, the two affected endpoints originate revised LSAs.

### Route validity

Unavailable links are excluded. Distance Vector path extraction checks each next hop and rejects loops or failed links. Unreachable destinations retain infinite cost and no route.

## 11. Implementation

The project uses Python 3 and type-annotated functions for the core data structures. The JSON file supplies every probability and link state, so route costs and output summaries are calculated by the algorithms rather than inserted as expected values. Tests check known ETX arithmetic, route selection, failures, recovery, message conventions, loop prevention, and repeated execution.

Control-message units are deliberately explicit:

- One Distance Vector message is one full vector sent over one directed active neighbor link in one round. The unchanged confirmation round counts.
- One Link State message is one LSA copy sent over one directed active link. A transmission is counted even if the receiving router already has that LSA; duplicate receipt is not forwarded again.
- Rounds count synchronous flooding/update steps. Initial rounds/messages are distinct from later event rounds/messages.
- A link event is reflected by a local adjacency change and endpoint LSA updates. The event itself is not counted as an extra packet.

These are transmission counts, not bytes, real control packets, or bandwidth estimates. Because one vector and one LSA differ in content and size, their message counts should not be read as a byte-for-byte overhead comparison.

## 12. Experimental Setup

The configured direct A-B link has delivery probabilities 0.55/0.55, making its ETX `1/(0.55*0.55)`. The A-B-D route has two hops, while A-E-F-D has three. Probabilities for the latter three links are 0.98/0.98. The code computes all route costs from those values and verifies that the two metrics actually choose different routes before saving results.

The experiments were executed with Python 3.12.0, NetworkX 3.7, Matplotlib 3.9.0, and Pytest 8.3.3. No real network hardware or packet traffic was used.

## 13. Results and Discussion

The values below were generated by running `python main.py` against the checked-in configuration. A round is protocol-specific and synchronous as defined above; it is not elapsed time.

### Initial A-to-D routes

| Algorithm | Metric | Selected path | Hops | Path ETX | Rounds | Messages |
|---|---|---|---:|---:|---:|---:|
| Distance Vector | Hop Count | A-B-D | 2 | 4.540353 | 3 | 60 |
| Distance Vector | ETX | A-E-F-D | 3 | 3.123698 | 4 | 80 |
| Link State | Hop Count | A-B-D | 2 | 4.540353 | 4 | 160 |
| Link State | ETX | A-E-F-D | 3 | 3.123698 | 4 | 160 |

This configuration demonstrates the central result: the minimum-hop path is one hop shorter but has higher total ETX. Both algorithms select the same path for a given metric in this network; that observation is specific to the topology.

### Link failure and recovery

| Stage | Algorithm | Metric | Selected path | Rounds | Messages |
|---|---|---|---|---:|---:|
| Failure | Distance Vector | Hop Count | A-E-F-D | 5 | 90 |
| Failure | Distance Vector | ETX | A-E-F-D | 2 | 36 |
| Failure | Link State | Hop Count | A-E-F-D | 5 | 36 |
| Failure | Link State | ETX | A-E-F-D | 5 | 36 |
| Recovery | Distance Vector | Hop Count | A-B-D | 4 | 80 |
| Recovery | Distance Vector | ETX | A-E-F-D | 2 | 40 |
| Recovery | Link State | Hop Count | A-B-D | 4 | 40 |
| Recovery | Link State | ETX | A-E-F-D | 4 | 40 |

The failure removes the initial Hop Count route but leaves an alternative route available. After recovery, the Hop Count route returns to A-B-D, while the ETX route remains A-E-F-D because it has lower ETX. The measured round/message differences are outcomes of this update model and topology; they do not establish that one protocol is generally faster or more expensive.

### Count to infinity

After R-S fails in the separate chain, the run without loop prevention records increasing Q/R estimates (3, 4, 5, …, 15) before the Hop Count limit makes the destination unreachable. Split horizon and poison reverse each withdraw the route without an increasing finite estimate beyond the post-failure stale value. In this experiment all three runs terminate; the two mechanisms prevent the demonstrated count-to-infinity sequence, not every possible routing loop.

### Figures and machine-readable data

- `results/convergence.png`: measured failure rounds across the four configurations.
- `results/message_overhead.png`: initial discovery, failure event, and recovery message counts.
- `results/path_quality.png`: measured ETX for paths selected with each metric.
- `results/topology.png`: eight-node graph with the initial Hop Count route and failed-then-restored A-B edge.
- `results/summary.csv`: all 12 configuration/stage records.

## 14. Limitations

The synchronous round model gives every node a common update boundary and does not model asynchronous delivery, timers, propagation, processing delays, or control-message loss. Therefore round counts cannot be interpreted as seconds and do not provide a real-time comparison. The topology is small, fixed, and undirected. Delivery probabilities remain deterministic and static. The control-message comparison counts transmissions rather than message sizes. Finally, the simplified protocol models illustrate their key mechanisms but are not complete RIP or OSPF standards implementations.

## 15. Conclusion

The implementation successfully compares two explicit routing algorithms across two metrics and link events. On the configured A-to-D network, Hop Count chooses A-B-D while ETX chooses the longer A-E-F-D route with lower computed ETX. A-B failure triggers an alternate route, and recovery restores the Hop Count preference. The separate chain exhibits count to infinity without loop prevention; split horizon and poison reverse stop that specific sequence. These conclusions apply to the executed simulation only.

## 16. References

1. D. S. J. De Couto, D. Aguayo, J. Bicket, and R. Morris, “A High-Throughput Path Metric for Multi-Hop Wireless Routing,” *Proceedings of the 9th Annual International Conference on Mobile Computing and Networking (MobiCom '03)*, 2003, pp. 134–146. DOI: [10.1145/938985.939000](https://doi.org/10.1145/938985.939000). Title, authors, pagination, and DOI checked against Crossref metadata.
2. G. Malkin, “RIP Version 2,” RFC 2453, Internet Engineering Task Force, November 1998. [https://www.rfc-editor.org/rfc/rfc2453](https://www.rfc-editor.org/rfc/rfc2453).
3. J. Moy, “OSPF Version 2,” RFC 2328, Internet Engineering Task Force, April 1998. [https://www.rfc-editor.org/rfc/rfc2328](https://www.rfc-editor.org/rfc/rfc2328).
4. J. J. Garcia-Luna-Aceves, “Loop-Free Routing Using Diffusing Computations,” *IEEE/ACM Transactions on Networking*, vol. 1, no. 1, pp. 130–141, 1993.
5. J. F. Kurose and K. W. Ross, *Computer Networking: A Top-Down Approach*, 8th ed., Pearson, 2021.

