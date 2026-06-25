#!/bin/bash
# Entrypoint for lightweight reranker service

set -euo pipefail

echo "Starting lightweight reranker service..."
echo "Model: ${RERANK_MODEL:-BAAI/bge-reranker-v2-m3}"
echo "Device: ${RERANK_DEVICE:-cuda}"
echo "Port: ${PORT:-8000}"

exec python /app/rerank_server.py