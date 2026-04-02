from __future__ import annotations

import math

import pytest

from memory.fragmentation import compute_metrics


def test_all_free_memory_has_zero_external_fragmentation():
    metrics = compute_metrics([(0, 128)])
    assert metrics.external_frag == 0.0


def test_fully_allocated_memory_has_zero_external_fragmentation():
    metrics = compute_metrics([])
    assert metrics.external_frag == 0.0


def test_checkerboard_pattern_produces_high_external_fragmentation():
    metrics = compute_metrics([(index * 2, 1) for index in range(10)])
    assert metrics.external_frag > 0.8


def test_entropy_of_single_free_extent_is_zero():
    metrics = compute_metrics([(0, 512)])
    assert metrics.entropy == pytest.approx(0.0, abs=1e-9)


def test_equal_sized_extents_have_log2_n_entropy():
    metrics = compute_metrics([(0, 10), (20, 10), (40, 10), (60, 10)])
    assert metrics.entropy == pytest.approx(math.log2(4), abs=1e-6)
