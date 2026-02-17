from __future__ import annotations
import subprocess
import sys
import re
from pathlib import Path

PY = sys.executable  # respects venv if activated, otherwise uses current python

SCENARIOS = [
    ("confidence", "serve", "KV-cache trace"),
    ("confidence", "demand", "KV-cache trace"),
    ("lru", "serve", "KV-cache trace"),
    ("lru", "demand", "KV-cache trace"),
]

TRACE = str(Path("traces") / "llm_kvcache_growth.jsonl")

PATTERNS = {
    "faults": re.compile(r"Faults:\s+(\d+)"),
    "migrations": re.compile(r"Migrations:\s+(\d+)"),
    "bytes_moved": re.compile(r"Bytes moved:\s+(\d+)"),
    "fallback_epochs": re.compile(r"Fallback epochs:\s+(\d+)"),
    "blocked_prefetch": re.compile(r"prefetch=(\d+)"),
    "blocked_evict": re.compile(r"evict=(\d+)"),
    "blocked_compact": re.compile(r"compact=(\d+)"),
    "lfe": re.compile(r"Fragmentation: LFE=(\d+)"),
    "holes": re.compile(r"holes=(\d+)"),
    "external_frag": re.compile(r"external_frag=([0-9\.]+)"),
}

def run(policy: str, miss: str) -> str:
    cmd = [PY, "run_sim.py", "--trace", TRACE, "--policy", policy, "--miss-mode", miss]
    out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    return out

def parse(out: str):
    def get(key, default=None):
        m = PATTERNS[key].search(out)
        return m.group(1) if m else default
    return {
        "faults": int(get("faults", 0)),
        "migrations": int(get("migrations", 0)),
        "bytes_moved": int(get("bytes_moved", 0)),
        "fallback_epochs": int(get("fallback_epochs", 0)),
        "blocked_prefetch": int(get("blocked_prefetch", 0)),
        "blocked_evict": int(get("blocked_evict", 0)),
        "blocked_compact": int(get("blocked_compact", 0)),
        "lfe": int(get("lfe", 0)),
        "holes": int(get("holes", 0)),
        "external_frag": float(get("external_frag", 0.0)),
    }

def main():
    rows=[]
    for policy, miss, note in SCENARIOS:
        out = run(policy, miss)
        m = parse(out)
        rows.append((policy, miss, m))

    # Print table
    header = ["policy","miss","faults","migrations","MB_moved","fallback_ep","blocked_pref","LFE","holes","ext_frag"]
    print("="*110)
    print("HBM Fragmentation Guard — Benchmark Table (KV-cache trace)")
    print("="*110)
    print("{:<10} {:<7} {:>6} {:>10} {:>9} {:>11} {:>12} {:>6} {:>6} {:>8}".format(*header))
    for policy, miss, m in rows:
        mb = m["bytes_moved"]/1e6
        print("{:<10} {:<7} {:>6} {:>10} {:>9.3f} {:>11} {:>12} {:>6} {:>6} {:>8.3f}".format(
            policy, miss, m["faults"], m["migrations"], mb, m["fallback_epochs"], m["blocked_prefetch"],
            m["lfe"], m["holes"], m["external_frag"]
        ))
    print("="*110)
    print("Tip: run the fragmentation stressor with --show-map for a visual memory-map demo.")
    print("  python run_sim.py --trace traces/fragmentation_stressor.jsonl --policy confidence --miss-mode demand --show-map")

if __name__ == "__main__":
    main()
