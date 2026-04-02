# Policies

The simulator ships with three policies:

- `confidence_gated`: the main invention, using confidence-bounded reuse forecasts to decide admission, eviction, pinning, and compaction requests.
- `lru`: a simple recency baseline that demand-loads on miss and evicts the oldest resident object first.
- `clockpro`: a CLOCK-Pro inspired adaptive baseline with separate hot and cold resident lists, promotion on reuse, and eviction from cold before hot.

## Comparison

| Policy | Admission Criterion | Eviction Criterion | Compaction Trigger | Thrash Budget Awareness | Reuse Forecast Dependency |
| --- | --- | --- | --- | --- | --- |
| `confidence_gated` | Admit when forecast lower bound exceeds `admit_lb` | Evict when forecast upper bound falls below `evict_ub` | Requests compaction when `LFE < upcoming_need` or `external_frag > 0.45`, but only runs in safe windows | Yes, via `SafetyGate` fallback blocking discretionary actions | Yes |
| `lru` | Admit on demand miss when the safety gate still allows action | Evict least-recently-used resident | None | Indirectly, because demand admission stops once fallback activates | No |
| `clockpro` | Admit new objects into the cold list on demand miss | Evict from cold tail; if cold is empty, demote hot first | None | Indirectly, because demand admission stops once fallback activates | No |

## Notes

### `confidence_gated`
This policy models the proposed HBM fragmentation guard. Forecast uncertainty matters twice: a conservative lower bound controls admission, while an upper bound controls eviction so short-term noise does not cause immediate churn. The policy can also pin strong candidates and request compaction when fragmentation starts to threaten upcoming allocations.

### `lru`
The LRU baseline is intentionally simple. It makes no distinction between objects that were touched once versus objects that have stable, repeated reuse. That makes it a useful recency-only comparison for demand-paging behavior.

### `clockpro`
The CLOCK-Pro baseline splits residents into cold and hot populations. New objects start cold, repeated touches promote them hot, and hot overflow is handled by demoting the oldest hot resident back into cold. This captures the classic “reuse must be earned” behavior while staying lightweight enough for the reference simulator.
