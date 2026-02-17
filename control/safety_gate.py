from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Budgets:
    max_migration_bytes: int
    max_faults: int

class SafetyGate:
    def __init__(self, budgets: Budgets):
        self.budgets = budgets
        self.reset_epoch()
    def reset_epoch(self):
        self.migration_bytes = 0
        self.faults = 0
        self.fallback = False
    def consume_migration(self, nbytes: int):
        self.migration_bytes += nbytes
        self._check()
    def consume_fault(self, n: int=1):
        self.faults += n
        self._check()
    def _check(self):
        if self.migration_bytes > self.budgets.max_migration_bytes or self.faults > self.budgets.max_faults:
            self.fallback = True
    def allow_action(self) -> bool:
        return not self.fallback
    def status(self) -> str:
        return f"mig={self.migration_bytes}/{self.budgets.max_migration_bytes} faults={self.faults}/{self.budgets.max_faults} fallback={self.fallback}"
