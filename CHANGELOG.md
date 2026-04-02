# Changelog

## v3.3
- Added the CLOCK-Pro adaptive baseline and exposed policy-specific benchmark metrics.
- Refactored the simulator around a reusable `simulate()` API while preserving the CLI.
- Added a full pytest suite, packaging metadata, benchmark regression baseline, and richer CI workflows.
- Added a Streamlit dashboard, four new workload traces, enhanced fragmentation/timeline visualizers, and a GitHub Pages microsite.
- Added a long-form technical blog post with structured metadata, canonical tags, Open Graph tags, and sitemap entries for SEO.

## v3.2
- Added Matplotlib visualizer (tools/visualize_fragmentation.py).
- Added synthetic LLM telemetry mocks (workloads/llama3_70b_inference_mock.jsonl).
- Added GitHub Actions CI (.github/workflows/test.yml).


## v3.1
- Added `bench.py` for one-command comparisons and a compact results table.
- Improved README for fast adoption and reproducibility.
- Added docs (`docs/`) for trace format, output interpretation, and extension points.

## v3.0
- Demand-mode semantics for confidence policy now default to **fallback-only** demand-load (preserves confidence gate).
- Added blocked-action counters: `blocked_prefetch`, `blocked_evict`, `blocked_compact`.
- Added `fragmentation_stressor.jsonl` trace.
