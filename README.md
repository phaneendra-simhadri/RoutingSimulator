# Distance Vector and Link State Routing Metric Simulator

## Overview

This local Python simulator compares Distance Vector (Bellman–Ford updates) and Link State (flooded link-state advertisements plus each router's own Dijkstra run) on the same deterministic, undirected eight-node network. It compares minimum-hop routing with Expected Transmission Count (ETX) routing under normal operation, a link failure, recovery, and a separate count-to-infinity example.

The project is an educational simulation. It does not configure routers, send real packets, or measure real-world latency or convergence time.

## Problem statement and objectives

A route with fewer links is not necessarily more reliable. Hop Count gives each available link cost 1, while ETX models expected transmission attempts as `1 / (forward_delivery * reverse_delivery)` and adds those costs along a route. The project demonstrates that routing metric choice and routing protocol are separate concerns: both protocols run with both metrics.

Objectives:

- Implement synchronous, neighbor-advertisement Distance Vector routing.
- Implement Link State advertisement flooding and independent per-node Dijkstra calculations.
- Measure route, convergence rounds, and simulated control-message transmissions.
- Exercise failure, recovery, an unreliable link, unreachable destinations, and loop-prevention behavior.
- Produce reproducible CSV data and plots from the executed experiment.

## Technology

- Python 3.11+ (validated with Python 3.12)
- NetworkX for topology representation and drawing; not used for shortest-path routing
- Matplotlib for plots
- Pytest for automated tests

## Project structure

```text
RoutingMetricSimulator/
|-- config.json
|-- distance_vector.py
|-- experiments.py
|-- link_state.py
|-- main.py
|-- metrics.py
|-- README.md
|-- report.md
|-- requirements.txt
|-- simulator.py
|-- topology.py
|-- viva_questions.md
|-- results/
|   |-- convergence.png
|   |-- message_overhead.png
|   |-- path_quality.png
|   |-- summary.csv
|   `-- topology.png
`-- tests/
    |-- test_distance_vector.py
    |-- test_experiments.py
    |-- test_failures.py
    |-- test_link_state.py
    `-- test_metrics.py
```

## Installation

From PowerShell in this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Python 3.11 or newer is supported. If PowerShell blocks activation, use the venv interpreter directly: `.\.venv\Scripts\python.exe`.

## Run and test

```powershell
python main.py
python -m pytest -q
```

Running the program prints the routes and measured values for all four combinations at each stage, then writes figures and `results/summary.csv`. Re-running with the same configuration is deterministic. The spring layout uses a fixed seed.

## Configuration and scenarios

`config.json` contains the eight nodes, undirected links, per-direction delivery probabilities, initial availability, source/destination, the failed link, and Distance Vector settings.

1. **Initial network:** each protocol and metric calculates its routes from A to D.
2. **Link failure:** A-B is disabled; the protocols update their retained state and choose an alternate route.
3. **Link recovery:** A-B is restored; routes are recalculated and compared with initial routes.
4. **Lossy-link comparison:** the configured A-B link makes the two-hop Hop Count route worse in ETX than the longer A-E-F-D route. The program checks this condition using computed path costs and stops with an explicit error if the scenario no longer demonstrates it.
5. **Count to infinity:** a separate P-Q-R-S chain loses R-S. The run without loop prevention shows increasing estimates until the Hop Count limit. Separate split-horizon and poison-reverse runs withdraw the route without the same increasing sequence. Poison reverse is not claimed to eliminate all routing loops in every topology.

## Measurement definitions and output

- A **Distance Vector round** is one synchronous exchange in which every currently connected router sends one complete vector to each direct neighbor and computes a new table from the previous round's advertisements. The final unchanged confirmation exchange is included in rounds and messages.
- A **Distance Vector control message** is one such directed full-vector transmission. Therefore, each active undirected link contributes two transmissions per round.
- A **Link State round** is one synchronous flooding step. A newly received LSA is forwarded once by that node to each active neighbor. A transmission is counted even when it reaches a node that already has that LSA; duplicate reception does not cause further forwarding. Initial topology discovery and later changed-LSA floods are both counted in their respective phase.
- An LSA is a node's current list of available adjacent links and their delivery probabilities. A link failure or recovery is modeled as revised LSAs from its two endpoints; no separate failure packet is added.
- The main CSV reports initial discovery, incremental failure handling, and incremental recovery separately. A destination with no route is represented as `UNREACHABLE`, with no hop count and infinite ETX/cost.
- Graph values are generated from the same run data as the CSV. The control-overhead graph labels each stage; the convergence graph compares failure-recovery rounds; the path-quality graph compares measured route ETX; the topology graph highlights the selected initial Hop Count route and the failed-then-restored link.

Generated files:

- `results/summary.csv`: one row for each of the four configurations at each of the three stages.
- `results/convergence.png`: convergence rounds after the link failure.
- `results/message_overhead.png`: initial, failure, and recovery control transmissions.
- `results/path_quality.png`: total ETX of the routes selected by the two routing metrics.
- `results/topology.png`: configured eight-node network.

## Known limitations

- Synchronous rounds are a logical abstraction; they do not model timers, propagation delay, CPU time, packet loss during control-plane exchange, or wall-clock convergence.
- Link delivery probabilities remain fixed during a run. ETX assumes independent transmissions and uses the product of forward and reverse delivery probabilities.
- The topology is undirected; availability changes are applied to both endpoints.
- The control-message conventions make the two protocols measurable, but a full Distance Vector vector and a single LSA have different sizes. Counts are transmissions, not bytes or bandwidth.
- Split horizon and poison reverse mitigate the demonstrated loop scenario but are not universal loop-free proofs.
- The selected Distance Vector Hop Count ceiling (16) is used for the count-to-infinity demonstration; it is not a general ETX bound.

## Literature and report

The detailed academic report is in [report.md](./report.md), with verified bibliographic information and a clear separation between measured results and protocol theory. Beginner-friendly viva answers are in [viva_questions.md](./viva_questions.md).
