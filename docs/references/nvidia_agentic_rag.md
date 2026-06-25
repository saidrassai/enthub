# NVIDIA RAG Architecture — Reference Summary

Source: NVIDIA open-source agentic RAG reference implementations.

## Architecture Shape

NVIDIA’s agentic RAG pattern uses a strict retrieval-augmented loop with
explicit evaluation at each stage. The system is composed of:
- `retriever` — hybrid BM25 + dense with explicit ACL filtering
- `reranker` — cross-encoder with configurable cutoff
- `evaluator` — standalone script scoring precision, recall, citation
  presence, and safety
- `planner` — explicit multi-hop planner with hard hop budget

## Evaluation-First Design

NVIDIA treats evaluation as a first-class artifact, not an afterthought:
- `golden_set.jsonl` is versioned and split by query class
- `run_eval.py` is a standalone script, not embedded in CI
- Metrics emitted as JSON with commit SHA, model versions, config snapshot
- Regression detected by comparing current run to prior run, not by eyeballing

## Planner Hard Limits

Multi-hop planner has a hard maximum tool calls / planner iterations per
query. No path is open-ended. If the planner exhausts the budget, the
pipeline returns `insufficient_evidence`.

## Embedding Model Swap Guard

NVIDIA treats embedding model swaps as a vector index migration event:
- New model requires a full re-embed pass before serving traffic
- Old embeddings must not be returned after swap
- Query cache is invalidated on model version change

## Key Patterns Adopted

1. Standalone eval script with versioned golden set
2. Hard planner hop budget with `insufficient_evidence` short-circuit
3. Embedding model swap treated as migration with cache invalidation
4. Per-run metadata: commit SHA, model versions, config snapshot, debt tickets

## Relation to `enterprise-rag-gain`

NVIDIA’s approach maps directly to skills:
- `enterprise-rag-gain` section 3 (evaluation harness, dataset split, scoring)
- `enterprise-rag-pipeline` section 4 (multi-hop planner hard limits)
- `enterprise-rag-triage` Vector/Cache bucket (embedding drift, HNSW index)
