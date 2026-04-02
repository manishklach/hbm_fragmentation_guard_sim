from __future__ import annotations

from control.safety_gate import Budgets, SafetyGate
from policy.confidence_gated import ConfidenceGatedPolicy, Forecast
from run_sim import SimulationConfig, simulate


def test_high_confidence_object_is_admitted_below_lb_threshold():
    policy = ConfidenceGatedPolicy(admit_lb=0.60)
    decision = policy.decide_on_touch("obj", False, Forecast(0.95, 0.05))
    assert decision.action == "admit"


def test_low_confidence_object_is_not_admitted_above_lb_threshold():
    policy = ConfidenceGatedPolicy(admit_lb=0.60)
    decision = policy.decide_on_touch("obj", False, Forecast(0.20, 0.30))
    assert decision.action == "noop"


def test_eviction_is_triggered_when_upper_bound_falls_below_threshold():
    policy = ConfidenceGatedPolicy(evict_ub=0.35)
    decision = policy.decide_on_touch("obj", True, Forecast(0.20, 0.05))
    assert decision.action == "evict"


def test_thrash_budget_decrements_on_each_discretionary_action():
    gate = SafetyGate(Budgets(max_migration_bytes=256, max_faults=4))
    gate.consume_migration(64)
    gate.consume_migration(64)
    assert gate.migration_bytes == 128


def test_budget_exhaustion_triggers_deterministic_fallback_path():
    trace = [
        {"t": 0, "event": "alloc", "id": "obj", "size": 64},
        {"t": 1, "event": "touch", "id": "obj", "mu": 0.10, "sigma": 0.10},
    ]
    result = simulate(
        trace,
        "confidence",
        SimulationConfig(miss_mode="demand", max_faults=0, epoch=100, capacity=256, reserve=0),
    )
    assert result.stats["faults"] == 1
    assert result.stats["admit"] == 1
    assert result.stats["migrations"] == 1


def test_compaction_is_not_triggered_outside_safe_window():
    trace = []
    for index, obj_id in enumerate(["a", "b", "c", "d", "e"]):
        trace.append({"t": index, "event": "alloc", "id": obj_id, "size": 20})
    offset = len(trace)
    for step, obj_id in enumerate(["a", "b", "c", "d", "e"], start=offset):
        trace.append({"t": step, "event": "touch", "id": obj_id, "mu": 0.95, "sigma": 0.05})
    trace.extend(
        [
            {"t": 10, "event": "free", "id": "b"},
            {"t": 11, "event": "free", "id": "d"},
            {"t": 12, "event": "touch", "id": "a", "mu": 0.95, "sigma": 0.05},
        ]
    )

    config = SimulationConfig(miss_mode="demand", capacity=120, reserve=0, epoch=100)
    result = simulate(trace, "confidence", config)
    assert result.stats["compact"] == 0


def test_compaction_is_triggered_inside_safe_window_when_fragmented():
    trace = []
    for index, obj_id in enumerate(["a", "b", "c", "d", "e"]):
        trace.append({"t": index, "event": "alloc", "id": obj_id, "size": 20})
    offset = len(trace)
    for step, obj_id in enumerate(["a", "b", "c", "d", "e"], start=offset):
        trace.append({"t": step, "event": "touch", "id": obj_id, "mu": 0.95, "sigma": 0.05})
    trace.extend(
        [
            {"t": 10, "event": "free", "id": "b"},
            {"t": 11, "event": "free", "id": "d"},
            {"t": 12, "event": "safe_window", "phase": "boundary"},
            {"t": 13, "event": "touch", "id": "a", "mu": 0.95, "sigma": 0.05},
        ]
    )

    config = SimulationConfig(miss_mode="demand", capacity=120, reserve=0, epoch=100)
    result = simulate(trace, "confidence", config)
    assert result.stats["compact"] >= 1
