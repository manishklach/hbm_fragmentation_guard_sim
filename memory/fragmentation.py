from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import math

@dataclass
class FragMetrics:
    total_free: int
    lfe: int
    external_frag: float
    entropy: float
    hole_count: int

def _entropy(ext_sizes: List[int]) -> float:
    total = sum(ext_sizes)
    if total <= 0:
        return 0.0
    ps = [s/total for s in ext_sizes if s>0]
    return -sum(p*math.log(p+1e-12, 2) for p in ps)

def compute_metrics(free_extents: List[Tuple[int,int]]) -> FragMetrics:
    sizes=[s for _,s in free_extents if s>0]
    total_free=sum(sizes)
    lfe=max(sizes, default=0)
    holes=len(sizes)
    external = 0.0 if total_free==0 else max(0.0, 1.0 - (lfe/total_free))
    ent=_entropy(sizes)
    return FragMetrics(total_free, lfe, external, ent, holes)
