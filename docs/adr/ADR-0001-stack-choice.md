# ADR-0001 — Canonical Stack Selection

Context: The enterprise agentic RAG system requires a bounded, auditable
technology stack. Multiple viable options exist for vector DB, task queue,
frontend framework, and auth provider. Without a single locked choice,
agents will diverge, the review checklist will fail, and debt will
accumulate.

Decision: Enforcement is as important as selection. The stack is fixed
until an ADR supersedes a layer.

## Options Considered

| Layer | Rejected | Accepted |
|-------|----------|----------|
| Vector | Qdrant, Weaviate, Pinecone | PostgreSQL + pgvector |
| Task queue | RQ, Dramatiq, process pools | Redis + Celery (thread-based workers) |
| Frontend | React SPA, Vue | Next.js App Router + TypeScript + Tailwind |
| Auth | Custom JWT tables, session cookies | OAuth2/OIDC first-class; local JWT mock in dev only |
| Observability | OpenTelemetry vendor export, Datadog agent | Structured JSON logs to internal sinks only |
| Agent runtime | LangChain agents, CrewAI | Hermes (host-agnostic skills) |

## Consequences

- pgvector is the only vector target; no abstraction wrapper is permitted.
- Celery workers must respect the Onyx POSIX signal handling pattern.
- Frontend is deployable to edge; backend is not.
- Any deviation requires a linked `DEBT-*` ticket with measured impact.

Status: accepted.
