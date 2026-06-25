# ENTHub

**Enterprise Agentic RAG — production-grade, multi-tenant, open source.**

Built on the NVIDIA RAG Blueprint. Contract-first. Sprint-based. Zero vendor lock-in.

---

## Run it

```bash
cd /home/ubuntu/projects/nvidia-agentic-rag
cp deploy/docker/.env.example deploy/docker/.env
cd deploy/docker
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

Verify: `curl http://localhost/health`

Replace `.env` secrets before any non-local deployment.

---

## Documentation

| Document | Purpose |
|---|---|
| [`docs/workflow.md`](docs/workflow.md) | **Day-by-day development workflow, sprint cadence, CI gates, agent responsibilities** |
| [`PRD.md`](PRD.md) | Business/technical boundaries (immutable) |
| [`CONTEXT.md`](CONTEXT.md) | Ubiquitous language and architectural rules (immutable) |
| [`AGENTS.md`](AGENTS.md) | Agent roles, boundaries, and skill loading |
| [`docs/adr/`](docs/adr/) | Architecture Decision Records |
| [`docs/references/`](docs/references/) | OSS reference summaries: Onyx, SurfSense, AnythingLLM, NVIDIA RAG |

---

## How to contribute

1. Read [`docs/workflow.md`](docs/workflow.md) — this is the source of truth for branch naming, ticket protocol, and merge rules.
2. Claim a ticket from Linear: **Project Hermes** ([open board](https://linear.app/saidrassaiworkspace/project/project-hermes-a7840060f893)).
3. Contracts first, implementation second. Human PM writes the skeleton; you fill in the code.
4. Every PR must pass CI (`lint-type-test` → `enterprise-rag-review` → `docker-build`) before merge.

---

## Stack highlights

- **LLM**: vLLM (Qwen2.5-32B-Instruct)
- **Embeddings**: txtai + BGE-M3
- **Vector DB**: Qdrant (multi-tenant)
- **Orchestration**: LangGraph plan-execute-reflect
- **Auth/RBAC**: Keycloak
- **Gateway**: Traefik (mTLS, rate limiting)
- **Observability**: Prometheus, Grafana, Langfuse
- **Guardrails**: Guardrails AI (PII, topic, hallucination, injection)

See [`docs/architecture.md`](docs/architecture.md) for the full diagram and data flows.

---

MIT License.
