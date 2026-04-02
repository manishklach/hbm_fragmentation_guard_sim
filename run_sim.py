from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List

from control.safety_gate import Budgets, SafetyGate
from control.scheduler import SafeWindowScheduler
from memory.allocator import ContiguousAllocator
from memory.fragmentation import FragMetrics, compute_metrics
from policy.baselines import LRUPolicy
from policy.clockpro import ClockProPolicy
from policy.confidence_gated import ConfidenceGatedPolicy, Forecast
from viz.ascii_map import render_map


@dataclass
class SimulationConfig:
    miss_mode: str = "serve"
    demand_fallback_only: bool = True
    capacity: int = 800
    reserve: int = 80
    epoch: int = 20
    max_migration_bytes: int = 180
    max_faults: int = 6
    admit_lb: float = 0.60
    evict_ub: float = 0.35
    confidence_z: float = 1.0
    clockpro_hot_fraction: float = 0.40
    clockpro_cold_fraction: float = 0.60


@dataclass
class TimelinePoint:
    t: int
    event: str
    obj_id: str | None
    phase: str | None
    occupancy: int
    external_frag: float
    entropy: float
    lfe: int
    holes: int
    faults: int
    migrations: int
    bytes_moved: int
    compaction: int
    in_safe_window: bool
    free_extents: list[tuple[int, int]] = field(default_factory=list)
    blocks: list[tuple[int, int, str]] = field(default_factory=list)


@dataclass
class SimResult:
    policy: str
    miss_mode: str
    config: SimulationConfig
    stats: dict[str, int]
    fragmentation: FragMetrics
    policy_metrics: dict[str, float | int]
    timeline: list[TimelinePoint]
    final_free_extents: list[tuple[int, int]]
    final_blocks: list[tuple[int, int, str]]
    final_map: str

    def to_benchmark_row(self) -> dict[str, float | int]:
        row: dict[str, float | int] = {
            "faults": self.stats["faults"],
            "migrations": self.stats["migrations"],
            "bytes_moved": self.stats["bytes_moved"],
            "fallback_epochs": self.stats["fallback_epochs"],
            "external_frag": self.fragmentation.external_frag,
            "lfe": self.fragmentation.lfe,
            "holes": self.fragmentation.hole_count,
            "entropy": self.fragmentation.entropy,
        }
        row.update(self.policy_metrics)
        return row


def load_trace(path: str | Path) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _snapshot(
    hbm: ContiguousAllocator,
    timeline: list[TimelinePoint],
    event: dict[str, Any],
    safe_window: bool,
    faults_delta: int = 0,
    migrations_delta: int = 0,
    bytes_moved_delta: int = 0,
    compaction_delta: int = 0,
):
    metrics = compute_metrics(hbm.extents_free())
    blocks = [
        (block.start, block.size, block.obj_id)
        for block in sorted(hbm.blocks.values(), key=lambda b: b.start)
    ]
    timeline.append(
        TimelinePoint(
            t=int(event.get("t", len(timeline))),
            event=str(event.get("event", "unknown")),
            obj_id=event.get("id"),
            phase=event.get("phase"),
            occupancy=hbm.used(),
            external_frag=metrics.external_frag,
            entropy=metrics.entropy,
            lfe=metrics.lfe,
            holes=metrics.hole_count,
            faults=faults_delta,
            migrations=migrations_delta,
            bytes_moved=bytes_moved_delta,
            compaction=compaction_delta,
            in_safe_window=safe_window,
            free_extents=list(hbm.extents_free()),
            blocks=blocks,
        )
    )


def _build_policy(policy_name: str, config: SimulationConfig):
    if policy_name == "confidence":
        return ConfidenceGatedPolicy(
            admit_lb=config.admit_lb,
            evict_ub=config.evict_ub,
            z=config.confidence_z,
        )
    if policy_name == "lru":
        return LRUPolicy()
    if policy_name == "clockpro":
        return ClockProPolicy(
            capacity=config.capacity,
            hot_fraction=config.clockpro_hot_fraction,
            cold_fraction=config.clockpro_cold_fraction,
        )
    raise ValueError(f"unsupported policy: {policy_name}")


def _policy_on_admit(policy_obj: Any, obj_id: str, size: int):
    try:
        policy_obj.on_admit(obj_id, size)
    except TypeError:
        policy_obj.on_admit(obj_id)


def _policy_remove(policy_obj: Any, obj_id: str):
    if hasattr(policy_obj, "remove"):
        policy_obj.remove(obj_id)
    elif hasattr(policy_obj, "lru") and obj_id in policy_obj.lru:
        del policy_obj.lru[obj_id]


def _admit_with_eviction(
    hbm: ContiguousAllocator,
    policy_obj: Any,
    obj_id: str,
    size: int,
    stats: dict[str, int],
    try_compact_then_alloc,
) -> tuple[bool, int, int, int]:
    ok, bytes_moved_delta, migrations_delta, compaction_delta = try_compact_then_alloc(obj_id, size)
    while not ok:
        victim = policy_obj.pick_victim()
        if victim is None:
            break
        if hbm.in_mem(victim):
            hbm.free(victim)
        stats["evict"] += 1
        ok, extra_bytes, extra_migrations, extra_compaction = try_compact_then_alloc(obj_id, size)
        bytes_moved_delta += extra_bytes
        migrations_delta += extra_migrations
        compaction_delta += extra_compaction

    if ok:
        _policy_on_admit(policy_obj, obj_id, size)
        stats["admit"] += 1
    else:
        stats["hbm_alloc_fail"] += 1
    return ok, bytes_moved_delta, migrations_delta, compaction_delta


def simulate(
    trace_events: Iterable[dict[str, Any]],
    policy: str,
    config: SimulationConfig | None = None,
) -> SimResult:
    cfg = config or SimulationConfig()
    hbm = ContiguousAllocator(cfg.capacity)
    obj_size: Dict[str, int] = {}

    safety = SafetyGate(
        Budgets(max_migration_bytes=cfg.max_migration_bytes, max_faults=cfg.max_faults)
    )
    sched = SafeWindowScheduler()
    policy_obj = _build_policy(policy, cfg)

    stats = {
        "alloc_events": 0,
        "free_events": 0,
        "faults": 0,
        "migrations": 0,
        "bytes_moved": 0,
        "admit": 0,
        "pin": 0,
        "evict": 0,
        "compact": 0,
        "hbm_alloc_fail": 0,
        "fallback_epochs": 0,
        "blocked_prefetch": 0,
        "blocked_evict": 0,
        "blocked_compact": 0,
    }
    timeline: list[TimelinePoint] = []
    event_i = 0
    upcoming_need = 0

    def try_compact_then_alloc(obj: str, size: int) -> tuple[bool, int, int, int]:
        ok = hbm.alloc(obj, size)
        bytes_moved_delta = 0
        migrations_delta = 0
        compaction_delta = 0
        if ok:
            return ok, bytes_moved_delta, migrations_delta, compaction_delta
        if not sched.can_compact():
            return False, bytes_moved_delta, migrations_delta, compaction_delta
        if not safety.allow_action():
            stats["blocked_compact"] += 1
            return False, bytes_moved_delta, migrations_delta, compaction_delta
        moved = hbm.compact(reserve=cfg.reserve)
        if moved > 0:
            safety.consume_migration(moved)
            stats["bytes_moved"] += moved
            stats["migrations"] += 1
            stats["compact"] += 1
            bytes_moved_delta += moved
            migrations_delta += 1
            compaction_delta += 1
        ok = hbm.alloc(obj, size)
        return ok, bytes_moved_delta, migrations_delta, compaction_delta

    for ev in trace_events:
        event_i += 1
        if event_i % cfg.epoch == 1:
            if safety.fallback:
                stats["fallback_epochs"] += 1
            safety.reset_epoch()
            sched.end_window()

        et = ev["event"]
        faults_delta = 0
        migrations_delta = 0
        bytes_moved_delta = 0
        compaction_delta = 0

        if et == "safe_window":
            sched.on_safe_window()
            _snapshot(hbm, timeline, ev, sched.in_safe_window)
            continue

        if et == "alloc":
            obj = ev["id"]
            size = int(ev["size"])
            obj_size[obj] = size
            stats["alloc_events"] += 1
            upcoming_need = max(upcoming_need, size)
            _snapshot(hbm, timeline, ev, sched.in_safe_window)
            continue

        if et == "free":
            obj = ev["id"]
            obj_size.pop(obj, None)
            if hbm.in_mem(obj):
                hbm.free(obj)
            _policy_remove(policy_obj, obj)
            stats["free_events"] += 1
            _snapshot(hbm, timeline, ev, sched.in_safe_window)
            continue

        if et != "touch":
            _snapshot(hbm, timeline, ev, sched.in_safe_window)
            continue

        obj = ev["id"]
        size = obj_size.get(obj, 20)
        in_hbm = hbm.in_mem(obj)
        mu = ev.get("mu")
        sigma = ev.get("sigma")
        fc = Forecast(float(mu), float(sigma)) if mu is not None and sigma is not None else None

        if not in_hbm:
            safety.consume_fault(1)
            stats["faults"] += 1
            faults_delta += 1

        if policy == "lru":
            if in_hbm:
                policy_obj.on_touch(obj)
            elif cfg.miss_mode == "demand":
                if not (safety.allow_action() and sched.can_prefetch()):
                    stats["blocked_prefetch"] += 1
                else:
                    ok, extra_bytes, extra_migrations, extra_compaction = _admit_with_eviction(
                        hbm, policy_obj, obj, size, stats, try_compact_then_alloc
                    )
                    if ok:
                        safety.consume_migration(size)
                        stats["bytes_moved"] += size
                        stats["migrations"] += 1
                        bytes_moved_delta += size + extra_bytes
                        migrations_delta += 1 + extra_migrations
                        compaction_delta += extra_compaction
                    else:
                        bytes_moved_delta += extra_bytes
                        migrations_delta += extra_migrations
                        compaction_delta += extra_compaction
            _snapshot(
                hbm,
                timeline,
                ev,
                sched.in_safe_window,
                faults_delta,
                migrations_delta,
                bytes_moved_delta,
                compaction_delta,
            )
            continue

        if policy == "clockpro":
            if in_hbm:
                policy_obj.on_touch(obj)
            elif cfg.miss_mode == "demand":
                if not (safety.allow_action() and sched.can_prefetch()):
                    stats["blocked_prefetch"] += 1
                else:
                    ok, extra_bytes, extra_migrations, extra_compaction = _admit_with_eviction(
                        hbm, policy_obj, obj, size, stats, try_compact_then_alloc
                    )
                    if ok:
                        safety.consume_migration(size)
                        stats["bytes_moved"] += size
                        stats["migrations"] += 1
                        bytes_moved_delta += size + extra_bytes
                        migrations_delta += 1 + extra_migrations
                        compaction_delta += extra_compaction
                    else:
                        bytes_moved_delta += extra_bytes
                        migrations_delta += extra_migrations
                        compaction_delta += extra_compaction
            _snapshot(
                hbm,
                timeline,
                ev,
                sched.in_safe_window,
                faults_delta,
                migrations_delta,
                bytes_moved_delta,
                compaction_delta,
            )
            continue

        decision = policy_obj.decide_on_touch(obj, in_hbm, fc)

        if decision.action == "admit":
            if not sched.can_prefetch():
                _snapshot(hbm, timeline, ev, sched.in_safe_window, faults_delta)
                continue
            if not safety.allow_action():
                stats["blocked_prefetch"] += 1
            else:
                (
                    ok,
                    extra_bytes,
                    extra_migrations,
                    extra_compaction,
                ) = try_compact_then_alloc(obj, size)
                bytes_moved_delta += extra_bytes
                migrations_delta += extra_migrations
                compaction_delta += extra_compaction
                if ok:
                    safety.consume_migration(size)
                    stats["bytes_moved"] += size
                    stats["migrations"] += 1
                    stats["admit"] += 1
                    bytes_moved_delta += size
                    migrations_delta += 1
                else:
                    stats["hbm_alloc_fail"] += 1
        elif decision.action == "pin":
            stats["pin"] += 1
        elif decision.action == "evict":
            if not sched.can_evict():
                _snapshot(hbm, timeline, ev, sched.in_safe_window, faults_delta)
                continue
            if not safety.allow_action():
                stats["blocked_evict"] += 1
            elif hbm.in_mem(obj):
                hbm.free(obj)
                stats["evict"] += 1

        if not in_hbm and cfg.miss_mode == "demand":
            allow_demand = not cfg.demand_fallback_only or safety.fallback
            if allow_demand and sched.can_prefetch() and not hbm.in_mem(obj):
                (
                    ok,
                    extra_bytes,
                    extra_migrations,
                    extra_compaction,
                ) = try_compact_then_alloc(obj, size)
                bytes_moved_delta += extra_bytes
                migrations_delta += extra_migrations
                compaction_delta += extra_compaction
                if ok:
                    stats["bytes_moved"] += size
                    stats["migrations"] += 1
                    stats["admit"] += 1
                    bytes_moved_delta += size
                    migrations_delta += 1
                else:
                    stats["hbm_alloc_fail"] += 1

        metrics = compute_metrics(hbm.extents_free())
        compaction_request = policy_obj.request_compaction(
            metrics.external_frag,
            metrics.lfe,
            upcoming_need,
        )
        upcoming_need = 0
        if compaction_request.action == "compact" and sched.can_compact():
            if not safety.allow_action():
                stats["blocked_compact"] += 1
            else:
                moved = hbm.compact(reserve=cfg.reserve)
                if moved > 0:
                    safety.consume_migration(moved)
                    stats["bytes_moved"] += moved
                    stats["migrations"] += 1
                    stats["compact"] += 1
                    bytes_moved_delta += moved
                    migrations_delta += 1
                    compaction_delta += 1

        _snapshot(
            hbm,
            timeline,
            ev,
            sched.in_safe_window,
            faults_delta,
            migrations_delta,
            bytes_moved_delta,
            compaction_delta,
        )

    final_metrics = compute_metrics(hbm.extents_free())
    if hasattr(policy_obj, "metrics"):
        policy_metrics = policy_obj.metrics()
    else:
        policy_metrics = {
            "hot_hit_rate": 0.0,
            "cold_hit_rate": 0.0,
            "promotions": 0,
            "demotions": 0,
        }

    final_blocks = [
        (block.start, block.size, block.obj_id)
        for block in sorted(hbm.blocks.values(), key=lambda b: b.start)
    ]
    return SimResult(
        policy=policy,
        miss_mode=cfg.miss_mode,
        config=cfg,
        stats=stats,
        fragmentation=final_metrics,
        policy_metrics=policy_metrics,
        timeline=timeline,
        final_free_extents=list(hbm.extents_free()),
        final_blocks=final_blocks,
        final_map=render_map(hbm),
    )


def _print_summary(result: SimResult, show_map: bool = False):
    stats = result.stats
    m = result.fragmentation
    print("=" * 72)
    print("HBM Fragmentation Guard — Simulator Summary")
    print("=" * 72)
    print(
        f"Policy: {result.policy}   Miss mode: {result.miss_mode}   "
        f"Demand-fallback-only: {result.config.demand_fallback_only}"
    )
    print(
        f"HBM Capacity: {result.config.capacity}  "
        f"HBM Used: {result.timeline[-1].occupancy if result.timeline else 0}  "
        f"HBM Free: {m.total_free}  Reserve: {result.config.reserve}"
    )
    print(
        f"Catalog events: alloc={stats['alloc_events']} free={stats['free_events']}  "
        f"Timeline points: {len(result.timeline)}"
    )
    print(
        f"Faults: {stats['faults']}  Migrations: {stats['migrations']}  "
        f"Bytes moved: {stats['bytes_moved']}"
    )
    print(
        f"Decisions: admit={stats['admit']} pin={stats['pin']} "
        f"evict={stats['evict']} compact={stats['compact']}"
    )
    print(
        f"Blocked actions: prefetch={stats['blocked_prefetch']} "
        f"evict={stats['blocked_evict']} compact={stats['blocked_compact']}"
    )
    print(
        f"HBM alloc failures: {stats['hbm_alloc_fail']}  "
        f"Fallback epochs: {stats['fallback_epochs']}"
    )
    if result.policy == "clockpro":
        print(
            "CLOCK-Pro stats: "
            f"hot_hit_rate={result.policy_metrics['hot_hit_rate']:.3f} "
            f"cold_hit_rate={result.policy_metrics['cold_hit_rate']:.3f} "
            f"promotions={result.policy_metrics['promotions']} "
            f"demotions={result.policy_metrics['demotions']}"
        )
    print("-" * 72)
    print(
        f"Fragmentation: LFE={m.lfe} holes={m.hole_count} "
        f"external_frag={m.external_frag:.3f} entropy={m.entropy:.3f}"
    )
    if show_map:
        print("-" * 72)
        print("Memory map (ASCII):")
        print(result.final_map)
    print("=" * 72)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True)
    parser.add_argument("--policy", choices=["confidence", "lru", "clockpro"], default="confidence")
    parser.add_argument(
        "--miss-mode",
        choices=["serve", "demand"],
        default="serve",
        help=(
            "On touch miss: 'serve' models stall/fault but does not force admission; "
            "'demand' models demand-load admission when allowed."
        ),
    )
    parser.add_argument(
        "--demand-fallback-only",
        action="store_true",
        default=True,
        help=(
            "(default on) For confidence policy in demand mode: only demand-load on miss "
            "if SafetyGate fallback is active."
        ),
    )
    parser.add_argument("--capacity", type=int, default=800)
    parser.add_argument("--reserve", type=int, default=80)
    parser.add_argument("--epoch", type=int, default=20)
    parser.add_argument("--max-migration-bytes", type=int, default=180)
    parser.add_argument("--max-faults", type=int, default=6)
    parser.add_argument("--admit-lb", type=float, default=0.60)
    parser.add_argument("--evict-ub", type=float, default=0.35)
    parser.add_argument("--show-map", action="store_true")
    parser.add_argument("--json", dest="json_path")
    return parser


def main(argv: list[str] | None = None):
    args = _build_arg_parser().parse_args(argv)
    config = SimulationConfig(
        miss_mode=args.miss_mode,
        demand_fallback_only=args.demand_fallback_only,
        capacity=args.capacity,
        reserve=args.reserve,
        epoch=args.epoch,
        max_migration_bytes=args.max_migration_bytes,
        max_faults=args.max_faults,
        admit_lb=args.admit_lb,
        evict_ub=args.evict_ub,
    )
    result = simulate(load_trace(args.trace), args.policy, config)
    _print_summary(result, show_map=args.show_map)
    if args.json_path:
        payload = {
            "policy": result.policy,
            "miss_mode": result.miss_mode,
            "config": asdict(result.config),
            "stats": result.stats,
            "fragmentation": asdict(result.fragmentation),
            "policy_metrics": result.policy_metrics,
            "timeline": [asdict(point) for point in result.timeline],
        }
        Path(args.json_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
