# =============================================================================
# LIGHTWEIGHT RERANKER SERVICE — sentence-transformers (BGE-Reranker-v2-M3)
# =============================================================================
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    fastapi==0.110.0 \
    uvicorn[standard]==0.29.0 \
    sentence-transformers==3.0.1 \
    torch==2.3.0 --extra-index-url https://download.pytorch.org/whl/cu121 \
    httpx==0.27.0 \
    pydantic==2.7.0

COPY rerank_server.py /app/
COPY rerank_entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]