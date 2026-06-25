# PRD: Enterprise Agentic RAG System (Project Hermes)

## 1. Vision & Mission
**Vision:** To provide enterprise teams with a fully private, permission-aware AI research assistant that delivers 100% cited, zero-hallucination answers over complex, fragmented internal data.

**Mission:** Build a production-grade Agentic RAG platform using a hybrid retrieval pipeline, strict governance boundaries, and autonomous agent workflows. The system will be built by a team of specialized Hermes AI agents, governed by senior engineering principles (YAGNI, TDD, Contract-First).

## 2. Target Audience & Personas
- **Knowledge Workers:** Need fast, accurate answers with verifiable citations to make decisions.
- **Security/Compliance Teams:** Require absolute guarantee that PII is redacted, access controls are enforced, and zero telemetry leaves the infrastructure.
- **IT/Admins:** Need a self-hostable system (Docker/K8s) that integrates with existing SSO (OIDC) and object storage (S3).

## 3. Core Capabilities (The "What")
1. **Plug-and-Pull Connectors:** Index data from SaaS apps (Drive, Confluence, Notion) and databases (Postgres) with incremental watermark sync.
2. **Hybrid Agentic Retrieval:** BM25 + Dense vector search, fused and processed through a mandatory cross-encoder reranker. An agentic loop handles multi-hop planning and full-document fetching.
3. **Strict Governance Layer:** Server-side RBAC/ACL enforcement at query time. PII redaction on inbound, outbound, and ingestion paths. Prompt injection defense.
4. **Cited Synthesis:** LLM generation is retrieval-gated. Every factual claim maps to `doc_id + chunk_id + span`. Finance/numeric paths require explicit unit verification.

## 4. Technical Boundaries (The "How")
- **Backend:** Python 3.13, FastAPI, SQLAlchemy 2, Celery, Redis.
- **Datastore:** PostgreSQL with `pgvector` (single vector target, no abstraction wrappers).
- **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS.
- **Infra:** Docker Compose (dev), Helm/Kubernetes (prod). 100% on-premise capable.
- **LLMs:** Model-agnostic. Support OpenAI API, local Ollama, or NVIDIA NIM endpoints via configuration.

## 5. Non-Goals (Out of Scope for V1)
- **General Chatbot:** This is not ChatGPT. Parametric-only answers are banned for factual queries.
- **Client-Side Policy Enforcement:** The frontend never dictates permissions.
- **Multi-Provider Vector Switching:** We use `pgvector`. Abstraction factories for vector DBs are banned.
- **Telemetry/Analytics:** Zero outbound network calls for usage tracking.

## 6. Success Metrics (The "Definition of Done")
- **Retrieval Precision@5:** >= 85% on the golden dataset.
- **Hallucination Rate:** <= 2% (measured by un-cited claims).
- **Citation Coverage:** 100% of factual answers have valid `doc_id` references.
- **Safety:** 0% PII leakage in outbound responses; 100% block rate on golden prompt-injection attacks.
- **Latency:** p95 <= 4s for single-hop; p95 <= 12s for multi-hop.

## 7. Milestones
- **M0: Scaffolding:** Repo setup, CI/CD, `docker-compose`, baseline eval harness.
- **M1: Ingestion Core:** File & Postgres connectors, structural chunking, `pgvector` indexing.
- **M2: Retrieval Core:** Hybrid BM25+Dense, mandatory reranker, ACL pre-filtering.
- **M3: Governance Core:** OIDC auth, PII redaction middleware, audit log.
- **M4: Agentic Loop & UI:** Multi-hop planner, Next.js chat interface, citation rendering.
