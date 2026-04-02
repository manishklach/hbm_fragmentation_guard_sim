# Extending the Harness

## Add a new trace

1. Create a generator under `workloads/` so the workload can be regenerated deterministically.
2. Write the emitted JSONL into `traces/` and keep it aligned to `traces/schema.json`.
3. Sanity-check it with:

```bash
python run_sim.py --trace traces/<your_trace>.jsonl --policy confidence --miss-mode demand --show-map
```

## Add a new policy

1. Add a file under `policy/`, for example `policy/my_policy.py`.
2. Keep the policy lightweight: admission hooks, touch hooks, and a victim picker are enough for most baselines.
3. Wire it into `run_sim.py` so both the CLI and `simulate()` can see it.
4. Add it to `bench.py` if it should appear in the canonical comparison table.

## Add richer visualization

The repository ships with both an ASCII map and two Matplotlib utilities:

```bash
python tools/visualize_fragmentation.py --trace traces/fragmentation_stressor.jsonl --policy confidence --out docs/img/fragmentation_demo.png
python tools/visualize_fragmentation.py --trace traces/fragmentation_stressor.jsonl --compare --out docs/img/fragmentation_compare.png
python tools/visualize_fragmentation.py --trace traces/fragmentation_stressor.jsonl --policy confidence --animate --out docs/img/fragmentation.gif
python tools/visualize_timeline.py --trace traces/llm_kvcache_growth.jsonl --policy clockpro --out docs/img/timeline.png
```

`visualize_fragmentation.py` supports `--policy`, `--compare`, `--animate`, and `--format` (`png`, `svg`, `gif`, `pdf`).

`visualize_timeline.py` produces a shared-x three-panel timeline:

- HBM occupancy over time
- `external_frag` over time with dashed threshold guides
- an event rug for alloc/free/touch/safe-window/compaction activity

Tip: keep default extensions dependency-light and prefer building on `run_sim.simulate()` so every surface stays consistent with the CLI.
