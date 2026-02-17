# Extending the Harness

## Add a new trace
1. Create a new `.jsonl` file in `traces/`.
2. Follow the schema in `traces/schema.json`.
3. Run:
```bash
python run_sim.py --trace traces/<your_trace>.jsonl --policy confidence --miss-mode demand --show-map
```

## Add a new policy
1. Add a file under `policy/`, e.g. `policy/my_policy.py`.
2. Implement a decision function similar to `ConfidenceGatedPolicy`.
3. Wire it into `run_sim.py` (CLI option).

## Add richer visualization
Today we ship an ASCII map (`viz/ascii_map.py`).
You can add:
- time-series CSV output
- matplotlib plots
- per-epoch logging

Tip: keep the default path dependency-light.
