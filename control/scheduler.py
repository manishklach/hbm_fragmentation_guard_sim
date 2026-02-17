from __future__ import annotations
from dataclasses import dataclass

@dataclass
class SafeWindowScheduler:
    allow_prefetch_outside_window: bool = True
    allow_evict_outside_window: bool = True
    in_safe_window: bool = False

    def on_safe_window(self):
        self.in_safe_window = True
    def end_window(self):
        self.in_safe_window = False
    def can_compact(self) -> bool:
        return self.in_safe_window
    def can_prefetch(self) -> bool:
        return self.allow_prefetch_outside_window or self.in_safe_window
    def can_evict(self) -> bool:
        return self.allow_evict_outside_window or self.in_safe_window
