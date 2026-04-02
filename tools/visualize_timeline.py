from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run_sim import SimulationConfig, load_trace, simulate


EVENT_COLORS = {
    "alloc": "#1F3A7A",
    "free": "#C0392B",
    "touch": "#2D8450",
}


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True)
    parser.add_argument("--policy", choices=["confidence", "lru", "clockpro"], default="confidence")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    result = simulate(load_trace(args.trace), args.policy, SimulationConfig(miss_mode="demand"))
    if not result.timeline:
        raise SystemExit("No timeline points available for plotting.")

    x_values = [point.t for point in result.timeline]
    occupancy = [point.occupancy for point in result.timeline]
    frag = [point.external_frag for point in result.timeline]

    figure, axes = plt.subplots(3, 1, figsize=(12, 8.5), sharex=True)

    axes[0].fill_between(x_values, occupancy, color="#90B9FF", alpha=0.6)
    axes[0].plot(x_values, occupancy, color="#1F3A7A", linewidth=2.0)
    axes[0].set_ylabel("HBM bytes")
    axes[0].set_title(f"HBM Timeline ({args.policy})")

    axes[1].plot(x_values, frag, color="#E8593C", linewidth=2.0, label="external_frag")
    axes[1].axhline(
        result.config.admit_lb,
        color="#1F3A7A",
        linestyle="--",
        linewidth=1.2,
        label="LB threshold",
    )
    axes[1].axhline(
        result.config.evict_ub,
        color="#7B849A",
        linestyle="--",
        linewidth=1.2,
        label="UB threshold",
    )
    axes[1].set_ylabel("Fragmentation")
    axes[1].set_ylim(0, 1)
    axes[1].legend(loc="upper right")

    for point in result.timeline:
        if point.event in EVENT_COLORS:
            axes[2].axvline(
                point.t,
                color=EVENT_COLORS[point.event],
                ymin=0.1,
                ymax=0.45,
                alpha=0.75,
            )
        if point.event == "safe_window":
            axes[2].axvspan(point.t - 0.5, point.t + 0.5, color="#BDC3C7", alpha=0.45)
        if point.compaction:
            axes[2].axvline(point.t, color="#F39C12", ymin=0.55, ymax=0.95, linewidth=2.0)
    axes[2].set_yticks([])
    axes[2].set_ylabel("Events")
    axes[2].set_xlabel("Timestamp")

    figure.tight_layout()
    out_path = Path(args.out)
    figure.savefig(out_path, dpi=220)
    print(f"Wrote: {out_path.resolve()}")


if __name__ == "__main__":
    main()
