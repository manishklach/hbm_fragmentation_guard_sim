from __future__ import annotations

import pytest

from memory.allocator import AllocationError, ContiguousAllocator, DoubleFreeError
from memory.fragmentation import compute_metrics


def test_single_alloc_succeeds_and_occupies_correct_bytes(small_hbm):
    assert small_hbm.alloc("kv_0", 4096) is True
    assert small_hbm.used() == 4096
    assert small_hbm.free_bytes() == (1024 * 1024) - 4096


def test_exact_fill_leaves_zero_free_bytes():
    allocator = ContiguousAllocator(100)
    for index in range(5):
        allocator.alloc_or_raise(f"obj_{index}", 20)
    assert allocator.free_bytes() == 0


def test_alloc_beyond_capacity_raises_correct_exception():
    allocator = ContiguousAllocator(64)
    allocator.alloc_or_raise("fits", 64)
    with pytest.raises(AllocationError):
        allocator.alloc_or_raise("overflow", 1)


def test_free_restores_free_bytes_correctly():
    allocator = ContiguousAllocator(128)
    allocator.alloc_or_raise("tensor", 80)
    allocator.free_or_raise("tensor")
    assert allocator.free_bytes() == 128


def test_compaction_after_fragmentation_reduces_hole_count_to_one():
    allocator = ContiguousAllocator(400)
    for name in ("a", "b", "c"):
        allocator.alloc_or_raise(name, 100)
    allocator.free_or_raise("b")

    before = compute_metrics(allocator.extents_free())
    allocator.compact()
    after = compute_metrics(allocator.extents_free())

    assert before.hole_count == 2
    assert after.hole_count == 1


def test_lfe_after_compaction_equals_total_free_bytes():
    allocator = ContiguousAllocator(400)
    for name in ("a", "b", "c"):
        allocator.alloc_or_raise(name, 100)
    allocator.free_or_raise("b")
    allocator.compact()

    metrics = compute_metrics(allocator.extents_free())
    assert metrics.lfe == metrics.total_free


def test_double_free_raises_correct_exception():
    allocator = ContiguousAllocator(128)
    allocator.alloc_or_raise("tensor", 32)
    allocator.free_or_raise("tensor")
    with pytest.raises(DoubleFreeError):
        allocator.free_or_raise("tensor")
