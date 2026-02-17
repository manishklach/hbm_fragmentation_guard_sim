from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

@dataclass
class Block:
    start: int
    size: int
    obj_id: str

class ContiguousAllocator:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.blocks: Dict[str, Block] = {}

    def alloc(self, obj_id: str, size: int) -> bool:
        if obj_id in self.blocks:
            return True
        start = self._find_free_extent(size)
        if start is None:
            return False
        self.blocks[obj_id] = Block(start, size, obj_id)
        return True

    def free(self, obj_id: str):
        self.blocks.pop(obj_id, None)

    def in_mem(self, obj_id: str) -> bool:
        return obj_id in self.blocks

    def used(self) -> int:
        return sum(b.size for b in self.blocks.values())

    def free_bytes(self) -> int:
        return self.capacity - self.used()

    def extents_free(self) -> List[Tuple[int,int]]:
        used = sorted(self.blocks.values(), key=lambda b: b.start)
        ext=[]
        cur=0
        for b in used:
            if b.start > cur:
                ext.append((cur, b.start-cur))
            cur = max(cur, b.start+b.size)
        if cur < self.capacity:
            ext.append((cur, self.capacity-cur))
        return ext

    def largest_free_extent(self) -> int:
        return max((s for _,s in self.extents_free()), default=0)

    def _find_free_extent(self, size: int) -> Optional[int]:
        for start, sz in self.extents_free():
            if sz >= size:
                return start
        return None

    def compact(self, reserve: int=0) -> int:
        moved=0
        used = sorted(self.blocks.values(), key=lambda b: b.start)
        cursor=0
        for b in used:
            if cursor + b.size > self.capacity - reserve:
                cursor = b.start + b.size
                continue
            if b.start != cursor:
                moved += b.size
                self.blocks[b.obj_id] = Block(cursor, b.size, b.obj_id)
            cursor += b.size
        return moved
