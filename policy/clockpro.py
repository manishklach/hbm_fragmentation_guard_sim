from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional


@dataclass
class ClockProStats:
    hot_hits: int = 0
    cold_hits: int = 0
    promotions: int = 0
    demotions: int = 0
    touches: int = 0

    @property
    def hot_hit_rate(self) -> float:
        return 0.0 if self.touches == 0 else self.hot_hits / self.touches

    @property
    def cold_hit_rate(self) -> float:
        return 0.0 if self.touches == 0 else self.cold_hits / self.touches


class ClockProPolicy:
    """A simplified CLOCK-Pro inspired adaptive baseline.

    Objects begin in the cold list, are promoted to hot on reuse, and eviction
    is biased toward the oldest cold resident. Capacity targets are maintained
    in bytes so the policy adapts naturally to heterogeneous object sizes.
    """

    def __init__(self, capacity: int, hot_fraction: float = 0.40, cold_fraction: float = 0.60):
        self.capacity = capacity
        self.hot_fraction = hot_fraction
        self.cold_fraction = cold_fraction
        self.hot_target = int(capacity * hot_fraction)
        self.cold_target = max(0, capacity - self.hot_target)
        self.hot: "OrderedDict[str, int]" = OrderedDict()
        self.cold: "OrderedDict[str, int]" = OrderedDict()
        self.stats = ClockProStats()

    def on_touch(self, obj_id: str):
        self.stats.touches += 1
        if obj_id in self.hot:
            self.stats.hot_hits += 1
            self.hot.move_to_end(obj_id)
            return
        if obj_id in self.cold:
            self.stats.cold_hits += 1
            size = self.cold.pop(obj_id)
            self.hot[obj_id] = size
            self.hot.move_to_end(obj_id)
            self.stats.promotions += 1
            self._rebalance_hot()

    def on_admit(self, obj_id: str, size: int):
        if obj_id in self.hot or obj_id in self.cold:
            self.on_touch(obj_id)
            return
        self.cold[obj_id] = size
        self.cold.move_to_end(obj_id)

    def remove(self, obj_id: str):
        self.hot.pop(obj_id, None)
        self.cold.pop(obj_id, None)

    def pick_victim(self) -> Optional[str]:
        if not self.cold and self.hot:
            self._demote_oldest_hot()
        if not self.cold:
            return None
        victim, _ = self.cold.popitem(last=False)
        return victim

    def metrics(self) -> dict[str, float | int]:
        return {
            "hot_hit_rate": self.stats.hot_hit_rate,
            "cold_hit_rate": self.stats.cold_hit_rate,
            "promotions": self.stats.promotions,
            "demotions": self.stats.demotions,
        }

    def _hot_bytes(self) -> int:
        return sum(self.hot.values())

    def _demote_oldest_hot(self):
        if not self.hot:
            return
        obj_id, size = self.hot.popitem(last=False)
        self.cold[obj_id] = size
        self.cold.move_to_end(obj_id)
        self.stats.demotions += 1

    def _rebalance_hot(self):
        while self._hot_bytes() > self.hot_target and self.hot:
            self._demote_oldest_hot()
