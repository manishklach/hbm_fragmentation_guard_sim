# Interpreting Output

The simulator prints a summary block.

## Key counters

- **Faults**: number of touches to non-resident objects. Interpretable as stalls / sysmem access.
- **Migrations**: number of admission or relocation operations. This is a proxy for HBM bandwidth usage.
- **Bytes moved**: sum of migrated bytes + compaction relocation bytes (proxy).
- **Fallback epochs**: epochs where thrash budgets were exceeded. When in fallback, discretionary actions are blocked.
- **Blocked actions**: attempts suppressed due to SafetyGate fallback:
  - `blocked_prefetch`
  - `blocked_evict`
  - `blocked_compact`

## Fragmentation metrics
- **LFE**: Largest Free Extent (biggest contiguous hole).
- **holes**: count of free extents.
- **external_frag**: `1 - LFE/total_free` (0 means perfectly contiguous free space).
- **entropy**: entropy of free-extent size distribution; higher means more scattered.

## What "good" looks like (qualitatively)
- lower fallback epochs
- fewer blocked actions
- lower external fragmentation (higher LFE, fewer holes)
- fewer migrations for the same fault rate (or fewer faults at comparable migrations)

## Comparing policies
Use `bench.py` to run canonical comparisons and print a compact table.
