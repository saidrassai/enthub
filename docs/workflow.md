# ENTHub Workflow Blueprint: Day 0 to Production

This document is the **single source of truth** for how ENTHub gets built, maintained, and shipped. It is auto-generated from the project’s canonical artifacts (`PRD.md`, `CONTEXT.md`, `AGENTS.md`, Linear tickets, and the 18 Hermes skills).

---

## 1. Overview

ENTHub is an **enterprise agentic RAG platform** built by a team of specialized AI agents (Ingestor, Retriever, Governator, Synthesizer) orchestrated by a Human PM.

**Core constraints:**
- Private-first, zero telemetry, PII redaction mandatory.
- Hybrid retrieval (BM25 + Dense) with mandatory reranker.
- One-week sprint cadence; no code merges without passing CI.
- Contract-first: Human PM writes all contract skeletons; agents implement only within pre-defined boundaries.

**Authoritative artifacts (never edit in place — always version):**
- `PRD.md` — business/technical boundaries, success metrics, non-goals.
- `CONTEXT.md` — ubiquitous language and architectural rules.
- `AGENTS.md` — agent roles, boundaries, and responsibilities.
- `docs/adr/` — architecture decision records.
- `docs/workflow.md` — this document.

---

## 2. Day 0: Bootstrap

### 2.1 One-time environment setup

| Actor | Action |
|---|---|
| Human PM | 1. Provision VM or Kubernetes cluster. 2. Create GitHub repo (`enthub`). 3. Enable **SSH** key + **GitHub Actions** (`workflow` scope) in `gh auth login`. |
| Human PM | 4. Set `github` Linear integration (optional, for automatic issue linking). |
| Human PM | 5. Create Linear team **Project Hermes** + labels mapped 1:1 to the 18 skills. |
| Human PM | 6. Clone repo, install `python3`, `docker`, `docker-compose`, `gh`, `gh`. |
| Human PM | 7. Copy `deploy/docker/.env.example` → `.env`; fill secrets (DB URL, API keys, etc.). |

### 2.2 Repo skeleton (Sprint 0 — bag 1)

```
enthub/
├── PRD.md                 # business/technical boundaries (immutable)
├── CONTEXT.md             # ubiquitous language + rules (immutable)
├── AGENTS.md              # agent role slicings (immutable)
├── README.md              # on-ramp for humans
├── LICENSE                # MIT
├── .gitignore             # includes ENTHub_project/, */onyx/, */surfsense/, */anythingllm/
├── .github/
│   └── workflows/
│       └── ci.yml         # lint-type-test, enterprise-rag-review, docker-build
├── docs/
│   ├── adr/               # ADR-0001, ADR-0002, ...
│   ├── eval/
│   │   ├── golden_set.jsonl   # 70 balanced queries
│   │   └── rubric.md           # scoring criteria
│   ├── references/        # Onyx, SurfSense, AnythingLLM, NVIDIA RAG summaries
│   └── workflow.md        # this document
├── src/
│   ├── rag-api/           # FastAPI + Pydantic + LangGraph/LlamaIndex (future)
│   ├── ingestion/
│   │   ├── connector/     # CheckpointedConnectorWithPermSync implementations
│   │   ├── hotdir/        # filesystem watcher → DocumentEnvelope
│   │   └── staging/       # multi-tenant staging queue
│   ├── retriever/
│   │   ├── pipeline.py    # BM25 + Dense fusion → reranker
│   │   └── agent/         # multi-hop agent graph (MAX_ROUNDS=5)
│   ├── govern/            # RBAC, PII redaction, audit log, telemetry wall
│   └── frontend/          # Node.js/Next.js consumer only
├── config/                # Qdrant, Prometheus, Loki, Tempo manifests
├── deploy/
│   ├── docker/
│   │   ├── docker-compose.yml      # single-node dev stack
│   │   ├── docker-compose.cpu.yml
│   │   ├── docker-compose.gpu.yml
│   │   ├── Dockerfiles per microservice
│   │   ├── traefik/       # reverse proxy + TLS termination
│   │   └── scripts/
│   └── k8s/               # production overlays (future)
└── scripts/
    ├── run_eval.py        # retrieval/generation scoring harness
    ├── backup.sh
    ├── restore.sh
    ├── benchmark.py
    ├── provision-tenant.sh
    └── update-models.sh
```

### 2.3 Authoritative contract writing (Human PM only)

Before any implementation ticket is created, Human PM writes:

1. **PRD boundary statement** — what the feature does + what it explicitly does not do.
2. **CONTEXT.md glossary entries** — new terms, their exact spelling, and origin skill.
3. **Interface skeleton** — function/class signature with docstring only; **no body**.
4. **Test contract** — example inputs, expected outputs, error cases.
5. **ADR (if architecture changes)** — problem, options, decision, consequences.

This contract is committed to `main` before any agent work begins.

---

## 3. Daily Workflow

### 3.1 Sprint lifecycle (1 week)

**Monday — Sprint Planning (Human PM)**
1. Review Linear board for ` Ready for Agent ` tickets.
2. For each ticket:
   - Assign 1 primary skill tag (`connector`, `pipeline`, `safety`, etc.).
   - Write acceptance criteria in the ticket body.
   - Set `Ready for Agent` state.
3. Create Sprint X milestone in Linear with 3–6 tickets.

**Tuesday–Friday — Agent Execution**

```
Agent receives ticket via Linear webhook / query
    ↓
Agent loads required skills (per ticket label)
    ↓
Agent reads PRD.md + CONTEXT.md for latest boundaries
    ↓
Agent reads interface skeleton from ticket/contract
    ↓
-- Contract-First block --
Agent cannot modify contract; must ask Human PM via Linear ticket comment
    ↓
Agent writes failing test (TDD red)
    ↓
Agent implements minimum code to pass test (TDD green)
    ↓
Agent runs `python scripts/run_eval.py` locally (optional, if eval-relevant)
    ↓
Agent commits, pushes branch, opens PR linked to ticket
    ↓
CI runs: lint → type-check → test → enterprise-rag-review → docker-build
    ↓
Ticket status → `Agent Review`
    ↓
Human PM reviews PR for boundary violations (architecture/safety only)
    ↓
Merge to main → ticket → `In Progress` → `Done`
```

**Friday 16:00 — Sprint Review (Human PM + Agents)**
- Walk through merged PRs.
- Run `scripts/run_eval.py` end-to-end against `docs/eval/golden_set.jsonl`.
- Update `docs/eval/scoreboard.md` with Sprint X numbers.
- Celebrate or retro.

**Sunday 18:00 — Retro & Reset**
- Human PM writes sprint retro note (what worked, what blocked).
- Close or roll over incomplete tickets.
- Update Linear project board for next sprint.

### 3.2 Agent persona boundaries (never violated)

| Role | Linear Labels | Skills | Hard No |
|---|---|---|---|
| **Ingestor** | `ingest`, `connector`, `infra` | connector, tdd, domain | Touching LLM config, retrieval logic |
| **Retriever** | `retrieve`, `pipeline`, `rag` | pipeline, codebase-design, safety | Writing PRD or governance policies |
| **Governator** | `govern`, `safety`, `ops` | safety, architecture, debt | Adjusting RAG fusion weights |
| **Synthesizer** | `frontend`, `ui`, `ux` | implement, domain | Implementing RBAC or auth |

If a ticket falls outside these boundaries, Human PM re-tags or splits it before execution starts.

---

## 4. Implementation Protocol (per ticket)

### 4.1 Branch naming

```
type/issue-number-short-desc
  ├── feature/ING-101-hotdir-staging
  ├── bugfix/ING-104-permission-sync
  ├── chore/INFRA-2-docker-compose
  └── refactor/DEBT-3-tenant-isolation
```

### 4.2 Commit message convention

```
<type>(<scope>): <subject>
  │        │        │
  │        │        └─ imperative, lowercase, no period
  │        └─ affected module (connector, pipeline, safety, infra, eval)
  └─ type: feature | bugfix | chore | refactor | docs | test | ci
```

### 4.3 Pull request template

```markdown
## Summary
- Linked Linear: https://linear.app/…/issue/…
- Primary skill: `enterprise-rag-connector`
- Agent persona: Ingestor

## Contract check
- [ ] Interface signature matches ticket skeleton exactly
- [ ] No new public methods added beyond contract
- [ ] Docstrings include `@Contract` tag (type, depth, seam)

## Testing
- [ ] Unit tests pass (`pytest tests/unit/`)
- [ ] Integration tests pass (`./scripts/test_stack.sh`)
- [ ] Type-check clean (`ruff check`)

## Review checklist
- [ ] No identity from client headers (Governator double-check)
- [ ] No telemetry/net calls without approval
- [ ] `enterprise-rag-review` green on this PR
```

### 4.4 CI pipeline (`.github/workflows/ci.yml`)

Every PR must pass 3 gates **in order**:

1. **lint-type-test** — `ruff`, `mypy`, `pytest`, docker-build (staging only)
2. **enterprise-rag-review gate** — skill-specific lint:
   - `enterprise-rag-connector` schema validation
   - `enterprise-rag-pipeline` query lifecycle contract check
   - `enterprise-rag-safety` telemetry/redaction audit
   - `enterprise-rag-debt` ADR/exception tracking check
3. **docker-build** — build all service images, push to registry

No merges until all 3 gates are green.

---

## 5. Testing & Evaluation

### 5.1 Unit / integration layer

- **Location:** `tests/` per microservice.
- **Owner:** Agent implementing the ticket.
- **CI gating:** `pytest` must pass before PR open.
- **Fraud check (Ponytail rule):** no mocks that hide real behavior (e.g., no “retrieval always returns 3 docs”).

### 5.2 Eval harness (`scripts/run_eval.py`)

Runs `docs/eval/golden_set.jsonl` (70 queries, balanced classes) against a staging service.

**Scoring:**
- Retrieval: recall@5, MRR.
- Generation: citation hit rate, PII redaction rate, zero-telemetry audit.

**Cadence:**
- `eval-1` → always run before Sprint X promotion.
- Weekly canary board (`docs/eval/scoreboard.md`).

### 5.3 Contract-First enforcement

Every implementation must match a pre-existing skeleton. Exceptions require **ADR + Human PM approval** before code is written.

---

## 6. Deployment

### 6.1 Staging (every merged PR → auto-deploy)
- `docker-compose -f deploy/docker/docker-compose.cpu.yml up -d`
- Run `scripts/run_eval.py` against staging.
- If eval regresses: auto-create `DEBT-*` ticket.

### 6.2 Production (Sprint boundary)
- `update-models.sh` → pin new model IDs.
- `provision-tenant.sh` → add new tenant to Qdrant + Postgres.
- `backup.sh` → schedule via cron.
- **Promotion gated by:**
  1. `docs/eval/scoreboard.md` trend flat or up for 1 sprint.
  2. `enterprise-rag-review` green.
  3. Human PM sign-off.

---

## 7. Incident & Debt Workflow

- **Bug found in production** → ticket tagged `debt`, Human PM writes ADR/root-cause within 24 hours.
- **Architecture exception** → `DEBT-*` ticket, ADR, due-date mandate.
- **Telemetry violation (accidental outbound call)** → `CRITICAL` state; Human PM freezes merging until Governator root-causes and patches.

---

## 8. Day 1 onward: Example ticker tape

| Day | Actor | Action | Output |
|---|---|---|---|
| 0 | Human | `gh auth login --scopes repo,workflow` | SSH/PAT ready |
| 0 | Human | `git clone …` + `cp .env.example .env` | Local env |
| 0 | Human | PRD.md, CONTEXT.md, AGENTS.md committed | Baseline |
| 1 | Human | Write ADR-0003 (Ollama vs vLLM) | `docs/adr/ADR-0003.md` |
| 1 | Human | Create Linear sprint tickets (INFRA/DEBT/EVAL) | 6 tickets |
| 2 | Ingestor agent | Hotdir staging connector | `src/ingestion/staging/collector.py` |
| 2 | Retriever agent | BM25 + Dense fusion | `src/retriever/pipeline.py` |
| 3 | Governator agent | Zero-telemetry audit + PII rail | `src/govern/…` |
| 4 | Synthesizer agent | TypeScript `CitedSnippet` renderer | `src/frontend/…` |
| 5 | Human + agents | Sprint review + `run_eval.py` | scoreboard updated |

---

## 9. Anti-patterns (never do)

- **Never** merge a PR with a failing `enterprise-rag-review` gate.
- **Never** add a new public interface without a contract skeleton committed first.
- **Never** read identity from client headers in backend routes.
- **Never** import a dependency that makes network calls during import.
- **Never** commit external OSS clones (Onyx, SurfSense, AnythingLLM).
- **Never** change ticket-to-agent hard assignments; agents are freely claimable.

---

## 10. Quick reference: who owns what

| Concern | Owner |
|---|---|
| PRD / Context / ADRs | Human PM |
| Hotdir / Connector / DocumentEnvelope | Ingestor |
| Hybrid search / Reranker / Agent loop | Retriever |
| RBAC / PII / Audit / Docker/K8s | Governator |
| Frontend / Citations / UX | Synthesizer |
| Eval / Scoreboard | Human PM + Gain skill |
| Contracts + Skeletons | Human PM only |

---

> **This document is versioned in Git.** To propose a workflow change, file a Linear ticket with tag `workflow` and open a PR. Human PM merges after contract-first review.
