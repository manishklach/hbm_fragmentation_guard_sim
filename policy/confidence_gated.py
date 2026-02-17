from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class Forecast:
    mu: float
    sigma: float
    def lb(self, z: float) -> float:
        return max(0.0, min(1.0, self.mu - z*self.sigma))
    def ub(self, z: float) -> float:
        return max(0.0, min(1.0, self.mu + z*self.sigma))

@dataclass
class PolicyDecision:
    action: str   # noop/admit/pin/evict/compact
    reason: str

class ConfidenceGatedPolicy:
    """Confidence-gated hysteresis:
    - Admission uses Lower Bound (LB)
    - Eviction uses Upper Bound (UB) to reduce thrash
    """
    def __init__(self, admit_lb: float=0.60, evict_ub: float=0.35, z: float=1.0):
        self.admit_lb = admit_lb
        self.evict_ub = evict_ub
        self.z = z
        self.pinned: set[str] = set()

    def decide_on_touch(self, obj_id: str, in_hbm: bool, fc: Optional[Forecast]) -> PolicyDecision:
        if fc is None:
            return PolicyDecision('noop','no_forecast')
        lb = fc.lb(self.z); ub = fc.ub(self.z)

        if not in_hbm:
            if lb >= self.admit_lb:
                return PolicyDecision('admit', f'lb={lb:.2f}>=admit_lb')
            return PolicyDecision('noop', f'lb={lb:.2f}<admit_lb')

        if obj_id in self.pinned:
            if ub < (self.evict_ub*0.6):
                self.pinned.discard(obj_id)
                return PolicyDecision('evict', f'pinned_ub={ub:.2f}<hard_floor')
            return PolicyDecision('noop','pinned')

        if ub <= self.evict_ub:
            return PolicyDecision('evict', f'ub={ub:.2f}<=evict_ub')

        if lb >= (self.admit_lb + 0.15):
            self.pinned.add(obj_id)
            return PolicyDecision('pin', f'lb={lb:.2f} promote')

        return PolicyDecision('noop', f'hold lb={lb:.2f} ub={ub:.2f}')

    def request_compaction(self, frag_ratio: float, lfe: int, upcoming_need: int) -> PolicyDecision:
        if lfe < upcoming_need:
            return PolicyDecision('compact', f'lfe={lfe}<need={upcoming_need}')
        if frag_ratio > 0.45:
            return PolicyDecision('compact', f'frag_ratio={frag_ratio:.2f}>0.45')
        return PolicyDecision('noop','no_compaction')
