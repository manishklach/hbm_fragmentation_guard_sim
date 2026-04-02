from __future__ import annotations

from control.safety_gate import Budgets, SafetyGate


def test_budget_initialises_to_configured_maximum():
    gate = SafetyGate(Budgets(max_migration_bytes=180, max_faults=6))
    assert gate.budgets.max_migration_bytes == 180
    assert gate.budgets.max_faults == 6
    assert gate.migration_bytes == 0
    assert gate.faults == 0


def test_budget_decrements_correctly_per_action_type():
    gate = SafetyGate(Budgets(max_migration_bytes=100, max_faults=3))
    gate.consume_migration(40)
    gate.consume_fault()
    assert gate.migration_bytes == 40
    assert gate.faults == 1
    assert gate.allow_action() is True


def test_fallback_mode_activates_at_zero_budget():
    gate = SafetyGate(Budgets(max_migration_bytes=0, max_faults=0))
    gate.consume_fault()
    assert gate.fallback is True


def test_fallback_mode_deactivates_on_epoch_reset():
    gate = SafetyGate(Budgets(max_migration_bytes=0, max_faults=0))
    gate.consume_fault()
    gate.reset_epoch()
    assert gate.fallback is False
    assert gate.migration_bytes == 0
    assert gate.faults == 0
