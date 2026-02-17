from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from collections import OrderedDict

@dataclass
class PolicyDecision:
    action: str
    reason: str

class LRUPolicy:
    def __init__(self):
        self.lru = OrderedDict()
    def on_touch(self, obj_id: str):
        if obj_id in self.lru:
            self.lru.move_to_end(obj_id)
    def on_admit(self, obj_id: str):
        self.lru[obj_id] = None
        self.lru.move_to_end(obj_id)
    def pick_victim(self) -> Optional[str]:
        if not self.lru:
            return None
        victim, _ = self.lru.popitem(last=False)
        return victim

class GreedyPrefetchPolicy:
    def __init__(self, mu_thresh: float=0.65):
        self.mu_thresh = mu_thresh
    def decide(self, in_hbm: bool, mu: Optional[float]) -> PolicyDecision:
        if in_hbm:
            return PolicyDecision('noop','already_in_hbm')
        if mu is None:
            return PolicyDecision('noop','no_mu')
        return PolicyDecision('admit' if mu >= self.mu_thresh else 'noop', f'mu={mu:.2f}')
