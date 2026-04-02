from __future__ import annotations

import pytest

from memory.allocator import ContiguousAllocator

collect_ignore_glob = ["dashboard/*"]


@pytest.fixture
def small_hbm():
    return ContiguousAllocator(1024 * 1024)


@pytest.fixture
def minimal_trace():
    return [
        {"t": 0, "event": "alloc", "id": "obj_a", "size": 64},
        {"t": 1, "event": "alloc", "id": "obj_b", "size": 64},
        {"t": 2, "event": "touch", "id": "obj_a", "mu": 0.95, "sigma": 0.05, "phase": "warmup"},
        {"t": 3, "event": "touch", "id": "obj_b", "mu": 0.85, "sigma": 0.05, "phase": "warmup"},
        {"t": 4, "event": "safe_window", "phase": "boundary"},
        {"t": 5, "event": "touch", "id": "obj_a", "mu": 0.90, "sigma": 0.05, "phase": "steady"},
        {"t": 6, "event": "free", "id": "obj_b"},
        {"t": 7, "event": "alloc", "id": "obj_c", "size": 32},
        {"t": 8, "event": "touch", "id": "obj_c", "mu": 0.75, "sigma": 0.10, "phase": "steady"},
        {"t": 9, "event": "free", "id": "obj_a"},
    ]
