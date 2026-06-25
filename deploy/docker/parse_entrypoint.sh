#!/bin/bash
# Entrypoint for Marker PDF parser service

set -euo pipefail

echo "Starting Marker PDF parser service..."
echo "Port: ${PORT:-8000}"

exec python /app/parse_server.py