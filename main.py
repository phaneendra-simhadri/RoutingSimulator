"""Run all routing experiments and save measured results."""

from __future__ import annotations

from pathlib import Path

from experiments import run_experiments
from topology import Topology


def main() -> None:
    root = Path(__file__).resolve().parent
    topology, config = Topology.from_json(root / "config.json")
    result = run_experiments(topology, config, root / "results")
    print("=" * 74)
    print("Distance Vector vs Link State: Hop Count and ETX")
    print("=" * 74)
    print(f"Topology: {len(topology.nodes)} nodes, {len(topology.links)} configured links")
    print(f"Selected source/destination: {result['source']} -> {result['destination']}")
    for stage in ("initial", "failure", "recovery"):
        print(f"\n{stage.upper()} NETWORK")
        for row in result["records"]:
            if row["stage"] != stage:
                continue
            print(
                f"  {row['algorithm']:15} {row['metric'].upper():4} "
                f"path={row['path']:12} hops={str(row['hop_count']):>2} "
                f"ETX={row['path_etx']:>8} rounds={row['convergence_rounds']:>2} "
                f"messages={row['control_messages']:>3}"
            )
    failed = " - ".join(result["failure"])
    print(f"\nLink event: {failed} failed, alternative routes remained reachable, then link recovered.")
    print("\nCOUNT-TO-INFINITY DEMONSTRATION (P-Q-R-S; R-S fails)")
    for mechanism, outcome in result["count_to_infinity"].items():
        updates = [
            f'{change["node"]}:{change["cost"]:.0f}'
            for change in outcome["changes"]
        ]
        print(
            f"  {mechanism:15} converged={outcome['converged']} "
            f"rounds={outcome['rounds']:2} P-to-S-reachable={outcome['reachable']} "
            f"Q/R cost updates={', '.join(updates) if updates else 'none'}"
        )
    print("\nGenerated results:")
    for filename in ("summary.csv", "convergence.png", "message_overhead.png", "path_quality.png", "topology.png"):
        print(f"  {root / 'results' / filename}")


if __name__ == "__main__":
    main()
