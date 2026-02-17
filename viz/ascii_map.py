from __future__ import annotations
from memory.allocator import ContiguousAllocator

def render_map(alloc: ContiguousAllocator, width: int=80) -> str:
    cap=alloc.capacity
    buf=['.']*width
    for obj,b in alloc.blocks.items():
        s=int((b.start/cap)*width)
        e=int(((b.start+b.size)/cap)*width)
        ch=obj[0].upper()
        for i in range(max(0,s), min(width, max(s+1,e))):
            buf[i]=ch
    return ''.join(buf)
