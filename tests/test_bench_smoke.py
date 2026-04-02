from __future__ import annotations

import subprocess
import sys


def test_bench_smoke_runs_without_traceback():
    completed = subprocess.run(
        [sys.executable, "bench.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0
    assert "confidence" in output
    assert "lru" in output
    assert "Faults" in output
    assert "external_frag" in output
    assert "Traceback" not in output
    assert "Error" not in output
