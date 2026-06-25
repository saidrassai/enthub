#!/bin/bash
# Entrypoint for txtai reranker service

set -euo pipefail

MODEL="${RERANK_MODEL:-BAAI/bge-reranker-v2-m3}"
DEVICE="${RERANK_DEVICE:-cpu}"
PORT="${PORT:-8000}"

echo "Starting txtai reranker service..."
echo "Model: ${MODEL}"
echo "Device: ${DEVICE}"
echo "Port: ${PORT}"

# Start txtai API server with reranker
exec python -m txtai.api \
    --model "${MODEL}" \
    --device "${DEVICE}" \
    --port "${PORT}" \
    --host 0.0.0.0 \
    --task rerank