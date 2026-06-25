# AnythingLLM Architecture — Reference Summary

Source: public AnythingLLM codebase and documentation.

## Architecture Shape

AnythingLLM is a full-stack RAG application with a strong emphasis on
multi-user isolation, hotdir ingestion, and plugin extensibility.

## Hotdir / Staging Pattern

AnythingLLM supports a filesystem-based ingestion pipeline:
1. User drops files into a watched directory (`hotdir/`)
2. Watcher detects new files, moves them to a staging area
3. Parser extracts text, chunks, embeds
4. Vector write completes
5. File moves to `processed/` or `failed/`

This pattern is useful for local-first or batch ingestion use cases.

## Multi-Tenant Workspace Model

AnythingLLM isolates data per `workspace`:
- Each workspace has its own vector collection namespace
- Embedding model and LLM settings are per-workspace
- Pinning is per-workspace, not global

## MCP Server Wrapper

AnythingLLM wraps external tools as MCP servers. The pattern:
- Tool definition is declared in a header block inside the markdown file
- Runner parses the header and exposes functions to the LLM
- Safety boundary: tools run in a sandboxed subprocess

## Key File Patterns

- `packages/desktop/server/stores/workspace.ts` — workspace settings
- `packages/desktop/server/utils/job.ts` — hotdir watcher + staging
- `packages/desktop/server/mcp.ts` — MCP server wrapper

## What to adopt

1. Hotdir/staging pattern for local or batch ingestion workflows
2. MCP server wrapper pattern for tool-calling over skills
3. Per-workspace vector namespace — useful for multi-tenant isolation
4. Header-declared tool definitions inside markdown knowledge files
