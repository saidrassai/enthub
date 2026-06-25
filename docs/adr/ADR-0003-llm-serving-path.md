# ADR-003: LLM Serving Path for Development Environment

## Status
Accepted

## Date
2026-06-25

## Author
Project Hermes / Human PM

---

## Context

The Operating Environment milestone requires a local LLM serving strategy for development, evaluation, and staging. Two viable paths were considered: **Ollama** and **vLLM**.

Selection must meet these constraints:
- Local or on-premise-first development
- Simple model-swap workflow (support Ollama registry, GGUF, and NVIDIA NIM-compatible endpoints)
- Low operational overhead for developer workstations
- Compatible with the enterprise gateway/agentic loop without introducing network telemetry
- Reasonable memory footprint on a single-node dev stack (Docker Compose)

## Options Considered

### Option A — Ollama
- Pros: one-command install, native model library (Llama, Mistral, Gemma, Qwen, DeepSeek-R1 distill variants), auto GGUF quantization, simple OpenAI-compatible local endpoint, tiny operational footprint.
- Cons: not optimized for large concurrent throughput; less configurable for production-grade batching/tensor parallelism.

### Option B — vLLM
- Pros: high throughput, PagedAttention, production-grade Kubernetes profiles, strong NVIDIA hardware tuning.
- Cons: heavier operational burden, requires GPU for meaningful throughput, slower local iteration on CPU, larger surface area for devbox mistakes.

## Decision

Use **Ollama** as the canonical **development environment LLM endpoint**.

Rationale:
- Development fidelity does not require vLLM throughput. Correctness of retrieval, safety rails, and citations matters more than tokens/sec during dev.
- Ollama matches the PRD’s “model-agnostic” requirement and lets engineers swap between OpenAI API, Ollama local, and NVIDIA NIM by changing config only.
- Keeps the dev Compose stack single-purpose and lightweight.

Production selection is deferred to a follow-up ADR when the infra ticket for staging/prod promotion is written.

## Consequences

- `deploy/docker/` compose scaffold will expose an `ollama` service with a default configurable model tag.
- `.env.example` / runtime `.env` will include `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` so the same code path drives dev/staging/prod.
- No hard dependency on NVIDIA GPUs in the dev environment.
- If production later selects vLLM, the agent code uses the same config keys; no rewrites required.

## References

- PRD.md §4 Technical Boundaries: “Model-agnostic. Support OpenAI API, local Ollama, or NVIDIA NIM endpoints via configuration.”
- docs/references/nvidia_agentic_rag.md: evaluation harness patterns.
