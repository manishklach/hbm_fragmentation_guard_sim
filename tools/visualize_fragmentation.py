"""
HBM Fragmentation Guard — Visualizer

Generates a simple Matplotlib heatmap showing HBM occupancy over time.
Safe-window events are marked as horizontal lines.

How to run (recommended, from repo root):
    python -m tools.visualize_fragmentation --trace traces/fragmentation_stressor.jsonl --out out_fragmentation.png

Notes:
- This visualizer uses a naive "admit on touch" rule to create an intuitive
  occupancy/fragmentation picture. Policy benchmarking remains in run_sim.py / bench.py.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path when running as a script:
# (python -m tools.visualize_fragmentation already works without this,
#  but this makes `python tools/visualize_fragmentation.py ...` work too.)
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import matplotlib.pyplot as plt

from memory.allocator import ContiguousAllocator
from memory.fragmentation import compute_metrics


def load_trace(path: str):
    """Yield JSON events from a JSONL file."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def render_state(hbm: ContiguousAllocator, width: int) -> np.ndarray:
    """
    Return a 1D occupancy array over HBM address space, binned to 'width'.
    Uses allocator's internal blocks map (obj_id -> Block).
    """
    cap = hbm.capacity
    bins = np.zeros(width, dtype=np.float32)
    scale = cap / width

    # ContiguousAllocator stores live allocations in hbm.blocks
    # where each block has .start and .size
    for blk in sorted(hbm.blocks.values(), key=lambda b: b.start):
        start = int(blk.start)
        size = int(blk.size)
        a = int(start / scale)
        b = int((start + size - 1) / scale)
        a = max(0, min(width - 1, a))
        b = max(0, min(width - 1, b))
        bins[a : b + 1] = 1.0

    return bins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True, help="Path to JSONL trace")
    ap.add_argument("--out", default="out_fragmentation.png", help="Output image file")
    ap.add_argument("--capacity", type=int, default=800, help="HBM capacity (bytes/units)")
    ap.add_argument("--width", type=int, default=140, help="Heatmap width (bins)")
    ap.add_argument("--every", type=int, default=1, help="Record every N events")
    args = ap.parse_args()

    trace_path = Path(args.trace)
    if not trace_path.exists():
        raise SystemExit(f"Trace not found: {trace_path}")

    hbm = ContiguousAllocator(args.capacity)

    # catalog sizes (objects exist in "system memory" regardless of residency)
    obj_size: dict[str, int] = {}

    frames: list[np.ndarray] = []
    safe_marks: list[int] = []

    i = 0
    for ev in load_trace(str(trace_path)):
        i += 1
        et = ev.get("event")

        if et == "alloc":
            obj_size[str(ev["id"])] = int(ev["size"])

        elif et == "free":
            oid = str(ev["id"])
            obj_size.pop(oid, None)
            if hbm.in_mem(oid):
                hbm.free(oid)

        elif et == "touch":
            # For visualization we "admit on touch" to show fragmentation evolution.
            oid = str(ev["id"])
            sz = int(obj_size.get(oid, 20))
            if not hbm.in_mem(oid):
                try:
                    hbm.alloc(oid, sz)
                except Exception:
                    # In a visualizer we tolerate allocation failures quietly.
                    pass

        elif et == "safe_window":
            # mark current frame index (where the line will be drawn)
            safe_marks.append(len(frames))

        if args.every <= 1 or (i % args.every == 0):
            frames.append(render_state(hbm, args.width))

    if not frames:
        raise SystemExit("No frames captured. Check trace path and --every.")

    H = np.stack(frames, axis=0)  # (time, width)

    fig = plt.figure(figsize=(10.5, 4.6))
    ax = fig.add_subplot(111)
    ax.imshow(H, aspect="auto", interpolation="nearest")
    ax.set_title("HBM Occupancy Heatmap (Trace-driven)")
    ax.set_xlabel("HBM address (binned)")
    ax.set_ylabel("time (frames)")

    for t in safe_marks:
        ax.axhline(t, linewidth=1)

    m = compute_metrics(hbm.extents_free())
    caption = (
        f"Final fragmentation: LFE={m.lfe}, holes={m.hole_count}, "
        f"external_frag={m.external_frag:.3f}, entropy={m.entropy:.3f}"
    )
    fig.text(0.01, 0.01, caption, fontsize=9)

    fig.tight_layout()
    out_path = Path(args.out)
    fig.savefig(str(out_path), dpi=220)
    print(f"Wrote: {out_path.resolve()}")


if __name__ == "__main__":
    main()
