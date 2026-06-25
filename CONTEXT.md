# CONTEXT.md: Enterprise RAG Ubiquitous Language & Rules

This document is the single source of truth for terminology and architectural constraints. All Hermes agents MUST use these terms exactly in code, commits, and PRs.

## 1. Domain Glossary

### Entities
- **Query:** The user's expressed information need, post-PII-sniff and post-RBAC-expansion. What the retrieval layer receives. *(Avoid: prompt, question)*
- **SentinelHit:** A guardrail match (PII, policy violation, injection) triggering a hard block rather than retrieval. *(Avoid: block, reject)*
- **ConnectorSeed:** The config triplet for a data source: `kind`, `config` (creds), `policy` (RBAC scope). *(Avoid: datasource, source)*
- **DocumentEnvelope:** The universal output of a connector: `normalized_text`, `source_meta`, `acls`, `source_ref`. *(Avoid: payload, chunk)*
- **ChunkCandidate:** A retrieval unit pre-RBAC filtering and reranking. *(Avoid: passage, segment)*
- **CitedSnippet:** A `ChunkCandidate` that survived RBAC, with provenance attached (`doc_id`, `span`, `tenant_scope`). *(Avoid: evidence, result)*
- **TenantScope:** The strict RBAC boundary. Cross-tenant leakage is a `SentinelHit`. *(Avoid: workspace, org)*

### Architecture Nouns
- **Module:** A unit of deployment with a public interface and hidden implementation. *(Avoid: component, service)*
- **Seam:** The boundary where two modules touch. The interface IS the test surface. *(Avoid: boundary, adapter)*
- **Depth:** Ratio of behavior to interface surface. Deep = small interface, large logic. *(Avoid: layer)*

## 2. Hard Architectural Rules

### A. Code Structure
1. Backend layout is exactly three vertical slices: `ingest/`, `retrieve/`, `govern/`.
2. No `utils/` or `helpers/` directories. Logic belongs to the module that owns the problem.
3. No generic ORM wrappers or Vector DB factories. Use SQLAlchemy and `pgvector` directly.
4. Every module exports a Pydantic schema or Python Protocol *before* implementation.

### B. Retrieval & Pipeline
1. **Hybrid First:** Default retrieval is BM25 (0.4) + Dense (0.6) via Reciprocal Rank Fusion.
2. **Mandatory Reranking:** Cross-encoder reranker is mandatory for multi-collection retrieval. Bypassing requires a `DEBT-*` ticket.
3. **ACL Pre-Filtering:** Unauthorized documents are discarded *before* ranking, not post-reranked. Enforced in the SQL/Vector query.
4. **Bounded Agentic Loop:** Multi-hop planning is bounded by `MAX_ROUNDS=5` and `MAX_TOKENS=20000`.

### C. Safety & Governance
1. **Server-Side Only:** RBAC and ACLs are enforced in `govern/`. Never trust client headers.
2. **Zero Telemetry:** No package may phone home. No third-party analytics. All metrics are internal JSON logs.
3. **PII Redaction:** Mandatory on inbound prompts, outbound responses, and document ingestion.
4. **Citation Gating:** LLM generation is retrieval-gated. Uncited factual claims are invalid output.

### D. Ponytail (Lazy Senior) Exclusions
These areas are NEVER candidates for LOC reduction:
- Table-aware chunk boundaries.
- Numeric verification and unit normalization.
- Calibration knobs for reranker cutoff.
- Export of raw evidence (provenance chain) for claims.
