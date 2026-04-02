from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from run_sim import SimulationConfig, load_trace, simulate

DEFAULT_TRACE = Path("traces") / "llm_kvcache_growth.jsonl"
POLICIES = ("confidence", "lru", "clockpro")


def run_benchmark(trace_path: str | Path = DEFAULT_TRACE) -> dict[str, dict[str, float | int]]:
    trace_events = load_trace(trace_path)
    results: dict[str, dict[str, float | int]] = {}
    for policy in POLICIES:
        result = simulate(trace_events, policy, SimulationConfig(miss_mode="demand"))
        results[policy] = result.to_benchmark_row()
    return results


def _format_metric(name: str, value: float | int | None) -> str:
    if value is None:
        return "-"
    if name in {"external_frag", "hot_hit_rate", "cold_hit_rate", "entropy"}:
        return f"{float(value):.3f}"
    if name == "bytes_moved":
        return f"{float(value) / 1e6:.3f} MB"
    return str(value)


def _print_table(results: dict[str, dict[str, float | int]], trace_path: str | Path):
    metrics = [
        ("Faults", "faults"),
        ("Migrations", "migrations"),
        ("Bytes moved", "bytes_moved"),
        ("Fallback epochs", "fallback_epochs"),
        ("external_frag", "external_frag"),
        ("LFE", "lfe"),
        ("Holes", "holes"),
        ("Entropy", "entropy"),
        ("Hot hit rate", "hot_hit_rate"),
        ("Cold hit rate", "cold_hit_rate"),
        ("Promotions", "promotions"),
        ("Demotions", "demotions"),
    ]
    print("=" * 90)
    print(f"HBM Fragmentation Guard — Benchmark Table ({trace_path})")
    print("=" * 90)
    print(f"{'Metric':<20} {'confidence':>16} {'lru':>16} {'clockpro':>16}")
    print("-" * 90)
    for label, key in metrics:
        values = [_format_metric(key, results[policy].get(key)) for policy in POLICIES]
        print(f"{label:<20} {values[0]:>16} {values[1]:>16} {values[2]:>16}")
    print("=" * 90)
    print(
        "Tip: use `python run_sim.py --trace traces/fragmentation_stressor.jsonl "
        "--policy clockpro --show-map` for an ASCII view."
    )


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", default=str(DEFAULT_TRACE))
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args(argv)

    results = run_benchmark(args.trace)
    _print_table(results, args.trace)

    if args.json_path:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "policies": {
                policy: {
                    "faults": int(metrics["faults"]),
                    "migrations": int(metrics["migrations"]),
                    "bytes_moved": int(metrics["bytes_moved"]),
                    "fallback_epochs": int(metrics["fallback_epochs"]),
                    "external_frag": float(metrics["external_frag"]),
                    "lfe": int(metrics["lfe"]),
                    "holes": int(metrics["holes"]),
                    "entropy": float(metrics["entropy"]),
                    "hot_hit_rate": float(metrics["hot_hit_rate"]),
                    "cold_hit_rate": float(metrics["cold_hit_rate"]),
                    "promotions": int(metrics["promotions"]),
                    "demotions": int(metrics["demotions"]),
                }
                for policy, metrics in results.items()
            },
        }
        Path(args.json_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
