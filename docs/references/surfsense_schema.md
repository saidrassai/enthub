# SurfSense Architecture — Reference Summary

Source: public SurfSense codebase and documentation.

## Architecture Shape

SurfSense is a lightweight, schema-first RAG framework oriented toward
research teams. It separates:
- `connectors/` — source adapters returning raw documents
- `processors/` — schema mapping and normalization
- `indexers/` — embedding and vector write
- `retrievers/` — BM25 + dense hybrid with optional reranker

## Schema Mapping Layer

SurfSense defines an explicit schema mapping between source fields and
canonical RAG fields:

| Source field | Canonical field | Notes |
|--------------|-----------------|-------|
| `title` | `metadata.title` | string |
| `body` / `content` | `normalized_text` | markdown or plain text |
| `url` | metadata.source_url | optional |
| `created_at` | metadata.last_indexed_at | ISO 8601 |
| `updated_at` | metadata.source_updated_at | ISO 8601 |

Schema mapping is a first-class config, not inline code.

## Connectors

- Connector returns raw documents, not envelopes.
- Processor layer normalizes documents into canonical envelope before index.
- Hydration is lazy: metadata is populated after chunk/embed, not at pull.

## Reranker

Reranker is optional by default. A reranker bypass is a first-class config
option, not a comment-out. This differs from Onyx’s mandatory default.

## Key File Patterns

- `surfsense/connectors/base.py` — base connector returning raw docs
- `surfsense/processors/schema.py` — field mapping rules
- `surfsense/retrievers/hybrid.py` — BM25 + dense blend

## What to adopt

1. Explicit schema mapping table in connector contract
2. Processor layer between connector pull and envelope emission
3. Lazy hydration pattern for large metadata payloads
