# HBM Fragmentation Guard — Reference Control Simulator (v3.1)

A **reference simulator + benchmark harness** for evaluating HBM residency-control policies and fragmentation behavior.
It is intentionally hardware-agnostic: no proprietary hooks required.

This repo models:
- probabilistic reuse forecasts with confidence bounds
- **confidence-gated hysteresis** (LB admission, UB eviction)
- a **thrash budget ledger** with deterministic fallback
- a simple contiguous HBM allocator + **fragmentation metrics**
- optional compaction only inside **safe windows**
- trace-driven “LLM-style” workload mocks

> **What it is not:** a device microcode implementation. It’s a policy simulator for reproducible evaluation.
>
> ## Disclaimer
This repository is provided for research and evaluation purposes only. It is **not production software** and is provided **“AS IS”** without warranties of any kind (including fitness for a particular purpose, accuracy, or non-infringement).  
No endorsement or affiliation with any HBM/GPU vendor is implied.  
This software license does **not** grant rights to any patents.


---

## Try It Now
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\bench.py
```

---

## Quickstart

### Windows PowerShell
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Compare confidence vs LRU under demand paging
.\.venv\Scripts\python.exe .\run_sim.py --trace .\traces\llm_kvcache_growth.jsonl --policy confidence --miss-mode demand
.\.venv\Scripts\python.exe .\run_sim.py --trace .\traces\llm_kvcache_growth.jsonl --policy lru --miss-mode demand
```

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python run_sim.py --trace traces/llm_kvcache_growth.jsonl --policy confidence --miss-mode demand
python run_sim.py --trace traces/llm_kvcache_growth.jsonl --policy lru --miss-mode demand
```

---

## One-command benchmark

Runs the canonical scenarios and prints a compact comparison table:

```bash
python bench.py
```

On Windows PowerShell (without activation):
```powershell
.\.venv\Scripts\python.exe .\bench.py
```

---

## What to look for in results

The simulator prints:
- **Faults** (serving from “system memory” / non-resident access)
- **Migrations / Bytes moved** (HBM fill/relocation proxy)
- **Fallback epochs** (budgets exceeded → discretionary actions blocked)
- **Fragmentation metrics**
  - `LFE`: largest free extent (contiguous space)
  - `holes`: number of free extents
  - `external_frag`: `1 - LFE/total_free`
  - `entropy`: entropy of free-extent sizes (higher = more scattered)

A typical desired pattern:
- confidence policy: fewer fallback epochs, fewer blocked actions, better fragmentation than LRU demand paging.

---

## CLI reference

### Policies
- `--policy confidence` — confidence-gated LB admission / UB eviction
- `--policy lru` — baseline LRU (demand paging only in demand mode)

### Miss modes
- `--miss-mode serve` — model misses as faults without forced admission
- `--miss-mode demand` — demand-load admission behavior

### Demand fallback-only (confidence policy)
By default, confidence policy in demand mode **only demand-loads after budgets are exceeded** (deterministic fallback path).
This preserves the confidence gate as the primary admission criterion.

---

## Repository layout

- `policy/`
  - `confidence_gated.py` — LB admission / UB eviction + compaction triggers
  - `baselines.py` — LRU baseline and simple greedy stub
- `control/`
  - `safety_gate.py` — thrash budgets + fallback
  - `scheduler.py` — safe-window gating
- `memory/`
  - `allocator.py` — contiguous allocator + compaction primitive
  - `fragmentation.py` — LFE/external frag/entropy metrics
- `viz/`
  - `ascii_map.py` — ASCII HBM map for quick inspection
- `traces/`
  - `schema.json` — JSONL trace schema
  - `llm_kvcache_growth.jsonl` — KV-cache growth mock
  - `moe_expert_swap.jsonl` — MoE swap mock
  - `fragmentation_stressor.jsonl` — designed to induce fragmentation

---

## Trace format (JSONL)

Each line is a JSON event:
- `t` : integer timestamp (arbitrary units)
- `event`: `alloc` | `free` | `touch` | `safe_window`
- `id` : object id (alloc/free/touch)
- `size`: object size (alloc)

Optional for `touch`:
- `mu`, `sigma`: reuse forecast parameters (mean/std-dev, 0..1)
- `phase`: label string

See: `traces/schema.json` and `docs/TRACE_FORMAT.md`.

---

## Documentation
- `docs/TRACE_FORMAT.md` — trace events + examples
- `docs/INTERPRETING_OUTPUT.md` — how to read the summary and compare policies
- `docs/EXTENDING.md` — adding traces, policies, and visualizations

---

## License
MIT (see `LICENSE`).
