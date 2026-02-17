# Trace Format (JSONL)

Traces are newline-delimited JSON records. Each record represents an event in a synthetic runtime.

## Required fields
- `t` (int): timestamp (arbitrary units)
- `event` (str): one of:
  - `alloc`: create an object in the global catalog (system memory)
  - `free`: delete an object from the catalog (and HBM if resident)
  - `touch`: access an object (may fault if not HBM-resident)
  - `safe_window`: marks that compaction is permitted (and optionally other expensive actions)

## Event schemas

### alloc
```json
{"t": 12, "event": "alloc", "id": "kv_17", "size": 25}
```

### free
```json
{"t": 150, "event": "free", "id": "kv_6"}
```

### touch
```json
{"t": 42, "event": "touch", "id": "param_3", "mu": 0.91, "sigma": 0.11, "phase": "train_step"}
```

`mu` and `sigma` represent a probabilistic forecast of reuse within the next horizon.

### safe_window
```json
{"t": 60, "event": "safe_window", "phase": "microbatch_boundary"}
```

Safe windows are used to gate compaction.

## Notes
- The simulator treats `alloc` as a catalog (system memory) creation only.
- HBM residency is driven by policy decisions on `touch` (and demand paging in demand mode).
