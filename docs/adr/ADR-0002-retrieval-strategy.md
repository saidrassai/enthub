# ADR-0002 — Hybrid Retrieval with Mandatory Cross-Encoder Reranking

Context: Retrieval quality is the strongest lever for reducing hallucination
and improving citation coverage. Dense-only retrieval underperforms on
entity-heavy queries and acronyms. Keyword-only retrieval misses synonyms.
Multi-collection retrieval increases noise and makes the reranker gate
critical.

Decision: Hybrid BM25 + dense is the default. Reranker is mandatory for
multi-collection and multi-hop. Dense-only or reranker-off are exceptions
that require a `DEBT-*` ticket with measured R@5 regression.

## Options Considered

| Strategy | Precision | Latency | Complexity | Verdict |
|----------|-----------|---------|------------|---------|
| Dense-only | Lower on entity queries | Lower | Lowest | Rejected |
| BM25-only | Lower on synonym queries | Lowest | Lowest | Rejected |
| Hybrid, no reranker | Medium | Medium | Low | Rejected for multi-collection |
| Hybrid + reranker | Highest | +150-300ms | Medium | Accepted |
| Hybrid + reranker + LLM reranker | Higher | +seconds | High | Deferred to future ADR |

## Mandatory Rules

1. Multi-collection retrieval must include reranker.
2. Multi-hop planner inherits the reranker gate from the last hop.
3. Disabling reranker for any path requires a `DEBT-*` ticket with R@5
   regression measurement and PM sign-off before merge.

## Consequences

- `pipeline` skill section 3 must describe reranker as
  "on by default, disable requires debt ticket" after this ADR.
- `gain` skill adds reranker latency target: <= 300ms for multi-collection.
- `review` and `grilling` skills gate reranker bypasses with this ADR.

Status: accepted.
