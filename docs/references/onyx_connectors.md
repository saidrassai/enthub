# Onyx Architecture — Reference Summary

Source: public Onyx codebase and documentation.

## Architecture Shape

Onyx is a three-service RAG platform:
- `ingestion-service` — pulls from connectors, chunks, embeds, writes to DB
- `api-service` — FastAPI; handles auth, query orchestration, response formatting
- `web-worker` / `celery` — background jobs for long-running pulls and model tasks

## Connector Modes (Onyx Taxonomy)

Onyx defines four connector interfaces:

- `LoadConnector` — polls source for changes; yields documents; uses watermarks
- `PollConnector` — repeatedly polls a static list; full listing each cycle
- `SlimConnector` — yields document ids only; ingestion service calls
  `pull_by_ids(ids)` for follow-up retrieval
- `CheckpointedConnectorWithPermSync` — persistent sync state outside ingestion
  service; connector must call `perm_sync()` to acknowledge safe checkpoint
  position before `pull()` advances

Relevant to our work:
- Connector taxonomy is first-class, not advisory.
- Checkpointed connectors own their durable sync position.
- Hook semantics: connector hooks are registered in ingestion service, not
  defined in connector code.

## Signal Handling

Onyx’s Celery workers use a supervisor pattern:
- A single parent process receives SIGTERM / SIGINT
- Parent propagates graceful shutdown to children
- Without this, workers become orphaned on deployment or scale-down

## Reranker Policy

Onyx treats reranker as mandatory for multi-collection retrieval. No
config flag disables it silently. If disabled, a tracked debt entry is
required.

## Relevance Classification

Onyx classifies retrieved documents before full read:
- `relevant` — pass to reranker and generation
- `partially relevant` — use for reranker context only
- `irrelevant` — discard before generation

This reduces read amplification and cost.

## Key File Patterns

- `onyx/connectors/connector.py` — base connector contract
- `onyx/connectors/models.py` — `ConnectorStatus`, `CredentialPair`
- `onyx/background/tasks.py` — Celery task definitions with signal handling
- `onyx/document_retrieval/` — retrieval service with hybrid BM25 + dense

## What to adopt (no code copied)

1. `LOAD / POLL / SLIM / CHECKPOINTED` mode enum
2. `SlimConnector.pull_ids()` as a first-class method
3. `CheckpointedConnectorWithPermSync.perm_sync()` contract
4. POSIX signal handling in Celery supervisor
5. Reranker mandatory default with debt ticket exception
6. Relevance classification before full-doc read
