from __future__ import annotations
import argparse, json
from typing import Dict
from policy.confidence_gated import ConfidenceGatedPolicy, Forecast
from policy.baselines import LRUPolicy
from control.safety_gate import SafetyGate, Budgets
from control.scheduler import SafeWindowScheduler
from memory.allocator import ContiguousAllocator
from memory.fragmentation import compute_metrics
from viz.ascii_map import render_map

def load_trace(path: str):
    with open(path,'r',encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if line:
                yield json.loads(line)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--trace', required=True)
    ap.add_argument('--policy', choices=['confidence','lru'], default='confidence')
    ap.add_argument('--miss-mode', choices=['serve','demand'], default='serve',
                    help="On touch miss: 'serve' models stall/fault but does not force admission; "
                         "'demand' models demand-load admission when allowed.")
    ap.add_argument('--demand-fallback-only', action='store_true', default=True,
                    help="(default on) For confidence policy in demand mode: only demand-load on miss if SafetyGate fallback is active. "
                         "This preserves the confidence gate as the primary admission criterion.")
    ap.add_argument('--capacity', type=int, default=800)
    ap.add_argument('--reserve', type=int, default=80)
    ap.add_argument('--epoch', type=int, default=20)
    ap.add_argument('--show-map', action='store_true')
    args=ap.parse_args()

    # HBM allocator (only HBM-resident objects consume this capacity)
    hbm=ContiguousAllocator(args.capacity)
    # Object catalog (represents the universe of objects in system memory)
    obj_size: Dict[str,int] = {}

    safety=SafetyGate(Budgets(max_migration_bytes=180, max_faults=6))
    sched=SafeWindowScheduler()

    conf=ConfidenceGatedPolicy()
    lru=LRUPolicy()

    stats={
        'alloc_events':0,'free_events':0,
        'faults':0,'migrations':0,'bytes_moved':0,
        'admit':0,'pin':0,'evict':0,'compact':0,
        'hbm_alloc_fail':0,'fallback_epochs':0,
        'blocked_prefetch':0,'blocked_evict':0,'blocked_compact':0
    }

    event_i=0
    upcoming_need=0

    def try_compact_then_alloc(obj: str, size: int) -> bool:
        ok = hbm.alloc(obj, size)
        if ok:
            return True
        # Try compaction only in safe window
        if sched.can_compact():
            if not safety.allow_action():
                stats['blocked_compact'] += 1
                return False
            moved = hbm.compact(reserve=args.reserve)
            if moved > 0:
                safety.consume_migration(moved)
                stats['bytes_moved'] += moved
                stats['migrations'] += 1
                stats['compact'] += 1
            ok = hbm.alloc(obj, size)
        return ok

    for ev in load_trace(args.trace):
        event_i += 1
        if event_i % args.epoch == 1:
            if safety.fallback:
                stats['fallback_epochs'] += 1
            safety.reset_epoch()
            sched.end_window()

        et=ev['event']
        if et=='safe_window':
            sched.on_safe_window()
            continue

        if et=='alloc':
            obj=ev['id']; size=int(ev['size'])
            obj_size[obj]=size
            stats['alloc_events'] += 1
            upcoming_need=max(upcoming_need, size)
            continue

        if et=='free':
            obj=ev['id']
            obj_size.pop(obj, None)
            if hbm.in_mem(obj):
                hbm.free(obj)
                if obj in getattr(lru, 'lru', {}):
                    try:
                        del lru.lru[obj]
                    except Exception:
                        pass
            stats['free_events'] += 1
            continue

        if et=='touch':
            obj=ev['id']
            size = obj_size.get(obj, 20)
            in_hbm=hbm.in_mem(obj)
            mu=ev.get('mu'); sigma=ev.get('sigma')
            fc=Forecast(float(mu), float(sigma)) if (mu is not None and sigma is not None) else None

            if not in_hbm:
                safety.consume_fault(1)
                stats['faults'] += 1

            # ---------------- LRU baseline ----------------
            if args.policy=='lru':
                if in_hbm:
                    lru.on_touch(obj)
                else:
                    if args.miss_mode=='demand':
                        if not (safety.allow_action() and sched.can_prefetch()):
                            stats['blocked_prefetch'] += 1
                            continue
                        ok = try_compact_then_alloc(obj, size)
                        if ok:
                            lru.on_admit(obj)
                            safety.consume_migration(size)
                            stats['bytes_moved'] += size
                            stats['migrations'] += 1
                            stats['admit'] += 1
                        else:
                            victim = lru.pick_victim()
                            if victim:
                                hbm.free(victim)
                                stats['evict'] += 1
                                ok = try_compact_then_alloc(obj, size)
                                if ok:
                                    lru.on_admit(obj)
                                    safety.consume_migration(size)
                                    stats['bytes_moved'] += size
                                    stats['migrations'] += 1
                                    stats['admit'] += 1
                            if not ok:
                                stats['hbm_alloc_fail'] += 1
                continue

            # ---------------- Confidence-gated policy ----------------
            dec = conf.decide_on_touch(obj, in_hbm, fc)

            # action gating: if fallback is active, all discretionary actions blocked
            # (except demand-load fallback path, when enabled)
            if dec.action=='admit':
                if not sched.can_prefetch():
                    continue
                if not safety.allow_action():
                    stats['blocked_prefetch'] += 1
                else:
                    ok = try_compact_then_alloc(obj, size)
                    if ok:
                        safety.consume_migration(size)
                        stats['bytes_moved'] += size
                        stats['migrations'] += 1
                        stats['admit'] += 1
                    else:
                        stats['hbm_alloc_fail'] += 1

            elif dec.action=='pin':
                stats['pin'] += 1

            elif dec.action=='evict':
                if not sched.can_evict():
                    continue
                if not safety.allow_action():
                    stats['blocked_evict'] += 1
                else:
                    if hbm.in_mem(obj):
                        hbm.free(obj)
                        stats['evict'] += 1

            # Demand-mode: optionally demand-load on miss.
            # For confidence policy we default to fallback-only demand load to preserve the confidence gate.
            if (not in_hbm) and args.miss_mode=='demand':
                allow_demand = True
                if args.demand_fallback_only:
                    allow_demand = safety.fallback  # demand-load only after budgets exceeded
                if allow_demand and sched.can_prefetch():
                    if not safety.allow_action():
                        # If we're in fallback, safety.allow_action() is False by definition.
                        # We still allow a minimal demand-load as a 'correctness path' (models deterministic fallback).
                        ok = try_compact_then_alloc(obj, size)
                        if ok:
                            # In fallback, we do NOT charge migration budget further; it is already exceeded.
                            stats['bytes_moved'] += size
                            stats['migrations'] += 1
                            stats['admit'] += 1
                        else:
                            stats['hbm_alloc_fail'] += 1

            # Compaction trigger (only in safe windows and only if not blocked)
            m=compute_metrics(hbm.extents_free())
            comp=conf.request_compaction(m.external_frag, m.lfe, upcoming_need)
            upcoming_need=0
            if comp.action=='compact' and sched.can_compact():
                if not safety.allow_action():
                    stats['blocked_compact'] += 1
                else:
                    moved=hbm.compact(reserve=args.reserve)
                    if moved>0:
                        safety.consume_migration(moved)
                        stats['bytes_moved'] += moved
                        stats['migrations'] += 1
                        stats['compact'] += 1

    m=compute_metrics(hbm.extents_free())
    print("="*72)
    print("HBM Fragmentation Guard — Simulator Summary")
    print("="*72)
    print(f"Policy: {args.policy}   Miss mode: {args.miss_mode}   Demand-fallback-only: {args.demand_fallback_only}")
    print(f"HBM Capacity: {args.capacity}  HBM Used: {hbm.used()}  HBM Free: {hbm.free_bytes()}  Reserve: {args.reserve}")
    print(f"Catalog objects: {len(obj_size)}  alloc_events: {stats['alloc_events']}  free_events: {stats['free_events']}")
    print(f"Faults: {stats['faults']}  Migrations: {stats['migrations']}  Bytes moved: {stats['bytes_moved']}")
    print(f"Decisions: admit={stats['admit']} pin={stats['pin']} evict={stats['evict']} compact={stats['compact']}")
    print(f"Blocked actions: prefetch={stats['blocked_prefetch']} evict={stats['blocked_evict']} compact={stats['blocked_compact']}")
    print(f"HBM alloc failures: {stats['hbm_alloc_fail']}  Fallback epochs: {stats['fallback_epochs']}")
    print("-"*72)
    print(f"Fragmentation: LFE={m.lfe} holes={m.hole_count} external_frag={m.external_frag:.3f} entropy={m.entropy:.3f}")
    if args.show_map:
        print("-"*72)
        print("Memory map (ASCII):")
        print(render_map(hbm))
    print("="*72)

if __name__=='__main__':
    main()
