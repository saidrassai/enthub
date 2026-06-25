#!/bin/bash
# Entrypoint for lightweight embeddings service

set -euo pipefail

echo "Starting lightweight embeddings service..."
echo "Model: ${EMBED_MODEL:-BAAI/bge-m3}"
echo "Device: ${EMBED_DEVICE:-cuda}"
echo "Port: ${PORT:-8000}"
echo "Batch size: ${BATCH_SIZE:-32}"

exec python /app/embed_server.py