from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run_sim import SimulationConfig, load_trace, simulate


def render_state(blocks: list[tuple[int, int, str]], capacity: int, width: int) -> np.ndarray:
    bins = np.zeros(width, dtype=np.float32)
    if capacity <= 0:
        return bins
    scale = capacity / width
    for start, size, _ in blocks:
        left = int(start / scale)
        right = int((start + size - 1) / scale)
        left = max(0, min(width - 1, left))
        right = max(0, min(width - 1, right))
        bins[left : right + 1] = 1.0
    return bins


def build_heatmap(result, width: int, stride: int = 1) -> np.ndarray:
    frames = [
        render_state(point.blocks, result.config.capacity, width)
        for point in result.timeline[::stride]
    ]
    return np.stack(frames, axis=0) if frames else np.zeros((1, width), dtype=np.float32)


def save_static_figure(results, out_path: Path, width: int, fmt: str):
    figure, axes = plt.subplots(1, len(results), figsize=(12, 4.8), squeeze=False)
    axes = axes[0]
    max_value = 1.0
    for axis, (policy, result) in zip(axes, results.items()):
        heatmap = build_heatmap(result, width)
        axis.imshow(heatmap, aspect="auto", interpolation="nearest", vmin=0, vmax=max_value)
        axis.set_title(f"HBM Occupancy Heatmap ({policy})")
        axis.set_xlabel("HBM address (binned)")
        axis.set_ylabel("time")
    figure.tight_layout()
    figure.savefig(out_path, dpi=220, format=fmt)


def save_animation(result, out_path: Path, width: int):
    figure, axis = plt.subplots(figsize=(10.5, 4.6))
    frames = [
        render_state(point.blocks, result.config.capacity, width)
        for point in result.timeline[::10]
    ]
    image = axis.imshow(
        np.expand_dims(frames[0], axis=0),
        aspect="auto",
        interpolation="nearest",
        vmin=0,
        vmax=1.0,
    )
    axis.set_title(f"HBM Occupancy Animation ({result.policy})")
    axis.set_xlabel("HBM address (binned)")
    axis.set_ylabel("frame")

    def update(frame_index: int):
        image.set_data(np.expand_dims(frames[frame_index], axis=0))
        axis.set_ylabel(f"frame {frame_index}")
        return [image]

    animation = FuncAnimation(figure, update, frames=len(frames), interval=180, blit=True)
    animation.save(out_path, writer=PillowWriter(fps=5))


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True, help="Path to JSONL trace")
    parser.add_argument("--out", default="out_fragmentation.png", help="Output path")
    parser.add_argument("--capacity", type=int, default=800, help="HBM capacity")
    parser.add_argument("--width", type=int, default=140, help="Heatmap width (bins)")
    parser.add_argument("--every", type=int, default=1, help="Record every N timeline points")
    parser.add_argument("--policy", choices=["confidence", "lru", "clockpro"], default="confidence")
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Render confidence and lru side-by-side",
    )
    parser.add_argument("--animate", action="store_true", help="Export an animated GIF")
    parser.add_argument("--format", choices=["png", "svg", "gif", "pdf"], default="png")
    args = parser.parse_args(argv)

    if args.compare and args.animate:
        raise SystemExit("--compare and --animate cannot be combined in the current visualizer.")

    trace = load_trace(args.trace)
    config = SimulationConfig(miss_mode="demand", capacity=args.capacity)

    if args.compare:
        results = {
            "confidence": simulate(trace, "confidence", config),
            "lru": simulate(trace, "lru", config),
        }
    else:
        results = {args.policy: simulate(trace, args.policy, config)}

    out_path = Path(args.out)
    if args.animate or args.format == "gif":
        result = next(iter(results.values()))
        save_animation(result, out_path, args.width)
    else:
        save_static_figure(results, out_path, args.width, args.format)
    print(f"Wrote: {out_path.resolve()}")


if __name__ == "__main__":
    main()
