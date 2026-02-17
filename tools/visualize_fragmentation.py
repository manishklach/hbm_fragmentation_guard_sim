"""HBM Fragmentation Guard — Visualizer

Generates a simple Matplotlib heatmap showing HBM occupancy over time.
Safe-window events are marked as horizontal lines.

Note: this visualizer uses a naive "admit on touch" rule to create an
intuitive occupancy/fragmentation picture. Policy benchmarking remains
in run_sim.py / bench.py.
"""

from __future__ import annotations
import argparse, json
import numpy as np
import matplotlib.pyplot as plt

from memory.allocator import ContiguousAllocator
from memory.fragmentation import compute_metrics

def load_trace(path: str):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if line:
                yield json.loads(line)

def render_state(hbm: ContiguousAllocator, width: int) -> np.ndarray:
    cap=hbm.capacity
    bins=np.zeros(width, dtype=np.float32)
    scale=cap/width
    for (start,size,_obj) in hbm.allocations():
        a=int(start/scale)
        b=int((start+size-1)/scale)
        a=max(0,min(width-1,a))
        b=max(0,min(width-1,b))
        bins[a:b+1]=1.0
    return bins

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--out", default="out_fragmentation.png")
    ap.add_argument("--capacity", type=int, default=800)
    ap.add_argument("--width", type=int, default=140)
    ap.add_argument("--every", type=int, default=1)
    args=ap.parse_args()

    hbm=ContiguousAllocator(args.capacity)
    obj_size={}
    frames=[]
    safe_marks=[]
    i=0
    for ev in load_trace(args.trace):
        i+=1
        et=ev["event"]
        if et=="alloc":
            obj_size[ev["id"]] = int(ev["size"])
        elif et=="free":
            oid=ev["id"]
            obj_size.pop(oid, None)
            if hbm.in_mem(oid):
                hbm.free(oid)
        elif et=="touch":
            oid=ev["id"]
            sz=obj_size.get(oid, 20)
            if not hbm.in_mem(oid):
                hbm.alloc(oid, sz)
        elif et=="safe_window":
            safe_marks.append(len(frames))

        if i % args.every == 0:
            frames.append(render_state(hbm, args.width))

    if not frames:
        raise SystemExit("No frames captured")

    H=np.stack(frames, axis=0)
    fig=plt.figure(figsize=(10.5,4.6))
    ax=fig.add_subplot(111)
    ax.imshow(H, aspect="auto", interpolation="nearest")
    ax.set_title("HBM Occupancy Heatmap (Trace-driven)")
    ax.set_xlabel("HBM address (binned)")
    ax.set_ylabel("time (frames)")
    for t in safe_marks:
        ax.axhline(t, linewidth=1)

    m=compute_metrics(hbm.extents_free())
    cap=f"Final fragmentation: LFE={m.lfe}, holes={m.hole_count}, external_frag={m.external_frag:.3f}, entropy={m.entropy:.3f}"
    fig.text(0.01,0.01,cap,fontsize=9)
    fig.tight_layout()
    fig.savefig(args.out, dpi=220)
    print(f"Wrote: {args.out}")

if __name__=="__main__":
    main()
