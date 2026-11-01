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

## 14. Volatility-Aware ETX Route-Selection Experiment

### Motivation and research question

The original experiments use static link delivery probabilities. In a dynamic network, a small improvement in the instantaneous ETX estimate can cause a source to alternate between routes even when the change is short-lived. Hysteresis can reduce such churn, but an overly large threshold can also keep a more expensive route after conditions improve. The question for this project-specific experiment is: **does adapting the route-switching threshold to recent link-quality variation reduce route changes relative to standard ETX while keeping path cost reasonable and preserving immediate rerouting when a selected link fails?**

This is an experimental extension, not a claim that hysteresis, smoothed metrics, or adaptive routing are new. RFC 6719 specifies the RPL Minimum Rank with Hysteresis Objective Function (MRHOF), which minimizes an additive metric while using hysteresis to reduce churn from small metric changes. RFC 8966 specifies Babel, a routing protocol designed for dynamic wired and wireless networks, with support for link-quality estimation and flexible metrics. These works establish relevant prior art; this project does not reproduce either protocol or claim priority over them.

### Scope and route-selection policies

The existing Link State + ETX implementation computes one current candidate path from A to D each simulation round. Three source-to-destination selectors consume the same candidate and the same topology trace:

1. **Standard ETX:** immediately selects the currently lowest-ETX candidate.
2. **Fixed-threshold ETX:** retains its current usable route unless the candidate's relative improvement reaches the configured threshold (default 10%).
3. **Volatility-aware ETX:** applies the same comparison with a threshold that increases with recent ETX fluctuations and decreases as the trace stabilizes.

Candidate-path calculation remains separate from the switching policy. This experiment evaluates a source-to-destination choice on top of Link State + ETX; it does not integrate the selectors into every router's distributed route-selection process. If the selected route becomes unavailable, a hysteresis policy switches to an available candidate immediately, irrespective of its threshold.

### Equations and parameters

For current route cost \(C\) and candidate cost \(C^*\), the relative improvement is

\[
I = \frac{C-C^*}{C}.
\]

The fixed policy switches when \(I \geq \theta_f\), with \(\theta_f=0.10\) by default. Equality is a switch, as covered by the boundary test.

For every link available in both consecutive rounds, the experiment measures relative ETX change \(r_{e,t}=|E_{e,t}-E_{e,t-1}|/E_{e,t-1}\), caps it at 1, and averages across those links to obtain \(x_t\). The EWMA volatility is

\[
v_t = \alpha x_t + (1-\alpha)v_{t-1}.
\]

When no link is available in both samples, the prior EWMA is retained. The adaptive threshold is

\[
\theta_t = \theta_{\min} +
\operatorname{clip}\left(\frac{v_t}{s},0,1\right)
(\theta_{\max}-\theta_{\min}).
\]

The default parameters are \(\theta_{\min}=0.02\), \(\theta_{\max}=0.45\), \(\alpha=0.30\), and scale \(s=0.08\). Thus stable conditions use a small threshold; volatility at or above \(s\) uses the maximum. All parameters, along with trial count, seed, and duration, can be set on the experiment command line. Availability transitions themselves are excluded from the volatility statistic; immediate failure handling is explicit, rather than encoded as a large quality fluctuation.

### Experimental setup and measurements

The extension keeps the configured eight nodes and uses five 80-round scenarios: low variability, high variability, gradual A-B deterioration, sudden severe A-B deterioration and restoration, and complete E-F failure followed by recovery. Each scenario is run for 30 trials with seeds 20261028 through 20261057. A trial's single generated trace and link events are applied identically to all three strategies. Delivery probabilities remain in \((0,1]\); complete failure is represented by the topology's availability flag.

- **Route switches:** number of changes in the selected path after its initial selection, including transitions to or from unreachable if they occur.
- **Average selected-route ETX:** arithmetic mean of the selected path's ETX over reachable rounds only.
- **Cumulative selected-route ETX:** sum of selected path ETX over reachable rounds; one simulation round is one equal-duration sample. Unavailable rounds are counted separately rather than added as infinity.
- **Unavailable-route rounds:** number of rounds with no selected usable path.
- **Failure response:** rounds from the E-F failure round to the first selected usable path that avoids E-F. **Recovery response:** rounds from restoration to the first selection of the pre-failure route. A response in the event round is zero rounds.
- **Control messages:** total transmissions counted by the existing Link State flooding model over the trace. It is the same for all three selectors and is not an estimate of extra traffic generated by a selector; the experiment adds no modeled policy-control messages.

The CSV stores trial seeds and raw measurements. Aggregate tables report the arithmetic mean and sample standard deviation across trials. Graphs are generated directly from these recorded values; the route timeline depicts the recorded default-seed high-variability trial.

### Results and discussion

The following are measured means and sample standard deviations across 30 trials, generated by `python volatility_experiment.py`:

| Scenario | Strategy | Route switches | Average selected ETX | Cumulative selected ETX |
|---|---|---:|---:|---:|
| High variability | Standard ETX | 39.03 ± 4.12 | 3.0585 ± 0.0101 | 244.68 ± 0.80 |
| High variability | Fixed-threshold ETX | 0.50 ± 0.51 | 3.1223 ± 0.0041 | 249.79 ± 0.33 |
| High variability | Volatility-aware ETX | 5.57 ± 2.62 | 3.1155 ± 0.0087 | 249.24 ± 0.70 |
| Gradual deterioration | Standard ETX | 1.00 ± 0.00 | 3.1044 ± 0.0002 | 248.35 ± 0.02 |
| Gradual deterioration | Fixed-threshold ETX | 1.00 ± 0.00 | 3.1176 ± 0.0003 | 249.41 ± 0.02 |
| Gradual deterioration | Volatility-aware ETX | 1.00 ± 0.00 | 3.1062 ± 0.0002 | 248.50 ± 0.02 |
| Sudden severe deterioration | Standard ETX | 2.00 ± 0.00 | 2.9073 ± 0.0000 | 232.58 ± 0.00 |
| Sudden severe deterioration | Fixed-threshold ETX | 2.00 ± 0.00 | 2.9073 ± 0.0000 | 232.58 ± 0.00 |
| Sudden severe deterioration | Volatility-aware ETX | 2.00 ± 0.00 | 2.9155 ± 0.0000 | 233.24 ± 0.00 |
| Failure and recovery | All three strategies | 2.00 ± 0.00 | 3.4657 ± 0.0000 | 277.26 ± 0.00 |

In the high-variability scenario, the adaptive policy reduced switches by about 86% relative to standard ETX (5.57 versus 39.03) while averaging ETX 3.1155, below the fixed policy's 3.1223. Standard ETX achieved the lowest average ETX (3.0585), showing the cost of hysteresis; the fixed policy switched even less than the adaptive policy in this particular trace family. Therefore the result supports reduced churn relative to the no-hysteresis baseline, not universal superiority over a fixed threshold.

The sudden-deterioration timeline also shows the opposite trade-off. When A-B's probability returned to 0.80 at round 53, standard and fixed-threshold ETX selected the newly better A-B-D route in that round. For the recorded adaptive trial, the threshold remained elevated: it retained A-E-F-D at rounds 53 and 54, switching at round 55. Across trials, its average ETX was 2.9155 rather than 2.9073. This is a measured example where volatility-aware stability delays a beneficial switch and slightly increases path cost.

During the complete E-F failure and recovery scenario, all strategies recorded zero unavailable-route rounds and zero-round response to both events. All had two route switches. This verifies immediate bypass and recovery for this connected topology. No route was unavailable in any measured trial. In the static low-variability case all policies selected the same path with no switches. Control-message counts were identical across strategies because all use the same Link State flooding trace; they measure the underlying modeled flooding only.

### Trade-offs and limitations

These are synthetic 8-node traces and 30 paired trials, not measurements from a live network. The random variation is limited to configured link probabilities; ETX still assumes independent transmissions and does not model packet sampling noise, traffic, timers, propagation, or actual convergence delay. The adaptive estimator observes aggregate link ETX changes at each simulation round, including links not on the selected route; another observation window or volatility statistic could yield different results. Its parameter values are illustrative and are not tuned or claimed optimal. The fixed policy performed especially well on route-switch count in the tested high-variability scenario, while standard ETX retained the lowest path cost. Failure response is measured in discrete rounds and is zero by construction when an alternative is available in the event round. Control-message counts exclude selector-specific communications because none are modeled. The policy operates only at the queried source/destination pair and is not a distributed routing-protocol modification.

The extension's command, configurable options, data files, and figures are described in the README. Its outputs are separate from the original static experiment.

## 15. Limitations

The synchronous round model gives every node a common update boundary and does not model asynchronous delivery, timers, propagation, processing delays, or control-message loss. Therefore round counts cannot be interpreted as seconds and do not provide a real-time comparison. The topology is small, fixed, and undirected. Delivery probabilities remain deterministic and static. The control-message comparison counts transmissions rather than message sizes. Finally, the simplified protocol models illustrate their key mechanisms but are not complete RIP or OSPF standards implementations.

## 16. Conclusion

The implementation successfully compares two explicit routing algorithms across two metrics and link events. On the configured A-to-D network, Hop Count chooses A-B-D while ETX chooses the longer A-E-F-D route with lower computed ETX. A-B failure triggers an alternate route, and recovery restores the Hop Count preference. The separate chain exhibits count to infinity without loop prevention; split horizon and poison reverse stop that specific sequence. These conclusions apply to the executed simulation only.

## 17. References

1. D. S. J. De Couto, D. Aguayo, J. Bicket, and R. Morris, “A High-Throughput Path Metric for Multi-Hop Wireless Routing,” *Proceedings of the 9th Annual International Conference on Mobile Computing and Networking (MobiCom '03)*, 2003, pp. 134–146. DOI: [10.1145/938985.939000](https://doi.org/10.1145/938985.939000). Title, authors, pagination, and DOI checked against Crossref metadata.
2. G. Malkin, “RIP Version 2,” RFC 2453, Internet Engineering Task Force, November 1998. [https://www.rfc-editor.org/rfc/rfc2453](https://www.rfc-editor.org/rfc/rfc2453).
3. J. Moy, “OSPF Version 2,” RFC 2328, Internet Engineering Task Force, April 1998. [https://www.rfc-editor.org/rfc/rfc2328](https://www.rfc-editor.org/rfc/rfc2328).
4. J. J. Garcia-Luna-Aceves, “Loop-Free Routing Using Diffusing Computations,” *IEEE/ACM Transactions on Networking*, vol. 1, no. 1, pp. 130–141, 1993.
5. J. F. Kurose and K. W. Ross, *Computer Networking: A Top-Down Approach*, 8th ed., Pearson, 2021.
6. O. Gnawali and P. Levis, “The Minimum Rank with Hysteresis Objective Function,” RFC 6719, Internet Engineering Task Force, September 2012. [https://www.rfc-editor.org/rfc/rfc6719](https://www.rfc-editor.org/rfc/rfc6719).
7. J. Chroboczek and D. Schinazi, “The Babel Routing Protocol,” RFC 8966, Internet Engineering Task Force, January 2021. [https://www.rfc-editor.org/rfc/rfc8966](https://www.rfc-editor.org/rfc/rfc8966).
