#!/usr/bin/env python3
# =============================================================================
# LIGHTWEIGHT RERANKER SERVER — sentence-transformers (BGE-Reranker-v2-M3)
# Provides API compatible with txtai rerank endpoint
# =============================================================================

import os
import asyncio
from typing import List, Tuple
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import CrossEncoder
import torch
import uvicorn


# Configuration
MODEL_NAME = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
DEVICE = os.getenv("RERANK_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
PORT = int(os.getenv("PORT", "8000"))

# Global model
model: CrossEncoder = None


class RerankRequest(BaseModel):
    query: str
    documents: List[str]
    top_n: int = 5


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    print(f"Loading reranker model: {MODEL_NAME} on {DEVICE}")
    model = CrossEncoder(MODEL_NAME, device=DEVICE)
    print(f"Reranker model loaded. Max length: {model.max_length}")
    yield
    print("Shutting down...")


app = FastAPI(title="Reranker Service", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "reranker", "model": MODEL_NAME, "device": DEVICE}


@app.post("/rerank")
async def rerank(request: RerankRequest):
    """Rerank documents for a query"""
    try:
        if not request.documents:
            return []
        
        # Create query-document pairs
        pairs = [(request.query, doc) for doc in request.documents]
        
        # Get scores
        scores = model.predict(pairs, batch_size=32, convert_to_numpy=True)
        
        # Get top_n indices sorted by score (descending)
        top_n = min(request.top_n, len(scores))
        ranked_indices = scores.argsort()[::-1][:top_n]
        
        # Return list of (index, score) tuples
        result = [(int(idx), float(scores[idx])) for idx in ranked_indices]
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)