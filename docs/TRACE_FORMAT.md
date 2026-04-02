# Trace Format (JSONL)

Traces are newline-delimited JSON records. Each record represents an event in a synthetic runtime.

## Required fields

- `t` (int): timestamp (arbitrary units)
- `event` (str): one of:
  - `alloc`: create an object in the global catalog (system memory)
  - `free`: delete an object from the catalog (and HBM if resident)
  - `touch`: access an object (may fault if not HBM-resident)
  - `safe_window`: marks that compaction is permitted

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

## Included workload models

### `llm_kvcache_growth.jsonl`
Mock KV-cache growth trace with repeated touches to a growing working set. This is the default quickstart trace and tends to show policy-level differences before severe fragmentation dominates.

### `moe_expert_swap.jsonl`
Synthetic mixture-of-experts swap trace with expert churn and reuse skew. Fragmentation appears as experts are loaded, touched, and retired over time.

### `fragmentation_stressor.jsonl`
Purpose-built trace for creating scattered free extents and exercising compaction. This is the fastest path to visualizing hole growth and `LFE` collapse.

### `transformer_prefill_decode.jsonl`
Models a transformer inference session with a clear prefill-to-decode transition. Prefill writes large KV-cache blocks with weak short-horizon reuse, then decode repeatedly revisits those KV blocks while short-lived activation buffers come and go, so fragmentation pressure tends to come from the activation churn around a long-lived resident KV set.

### `moe_load_imbalance.jsonl`
Models skewed MoE routing where 20% of experts absorb roughly 80% of touches. The hot experts should become strong residency candidates while cold experts create churn through periodic swap-ins and swap-outs, producing a useful baseline for comparing adaptive hot/cold policies.

### `multi_tenant_inference.jsonl`
Models three concurrent tenants sharing HBM with distinct behaviors: bursty low-reuse traffic, steady high-reuse traffic, and large moderate-reuse tensors. Expect cross-tenant interference, mixed-size holes, and more variable fragmentation than the single-tenant traces.

### `checkpoint_restore.jsonl`
Models training, checkpoint save, full restore, and resumed training. The save phase touches everything once with low reuse, restore reintroduces the working set in order, and safe windows between phases make this trace useful for observing whether compaction can cleanly prepare HBM for the next stage.
