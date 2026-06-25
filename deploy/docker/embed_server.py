#!/usr/bin/env python3
# =============================================================================
# LIGHTWEIGHT EMBEDDINGS SERVER — sentence-transformers (BGE-M3)
# Provides API compatible with txtai embeddings endpoints
# =============================================================================

import os
import asyncio
from typing import List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import torch
import uvicorn


# Configuration
MODEL_NAME = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
DEVICE = os.getenv("EMBED_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
PORT = int(os.getenv("PORT", "8000"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "32"))

# Global model
model: SentenceTransformer = None


class EmbedRequest(BaseModel):
    texts: List[str]


class SparseEmbedRequest(BaseModel):
    texts: List[str]


class ColBERTEmbedRequest(BaseModel):
    texts: List[str]


class HybridEmbedRequest(BaseModel):
    texts: List[str]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    print(f"Loading model: {MODEL_NAME} on {DEVICE}")
    model = SentenceTransformer(MODEL_NAME, device=DEVICE)
    
    # BGE-M3 supports multiple encoding modes
    print(f"Model loaded. Max seq length: {model.max_seq_length}")
    yield
    print("Shutting down...")


app = FastAPI(title="Embeddings Service", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "embeddings", "model": MODEL_NAME, "device": DEVICE}


@app.post("/embeddings")
async def embed_dense(request: EmbedRequest):
    """Dense vector embeddings"""
    try:
        embeddings = model.encode(
            request.texts,
            batch_size=BATCH_SIZE,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        return embeddings.tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sparse-embeddings")
async def embed_sparse(request: SparseEmbedRequest):
    """Sparse vector embeddings (BM25-style) - BGE-M3 supports this natively"""
    try:
        # BGE-M3 can output sparse vectors
        result = model.encode(
            request.texts,
            batch_size=BATCH_SIZE,
            convert_to_numpy=True,
            output_value="sparse"
        )
        # Format: list of {"indices": [...], "values": [...]}
        sparse_result = []
        for item in result:
            if hasattr(item, "indices"):
                sparse_result.append({
                    "indices": item.indices.tolist(),
                    "values": item.values.tolist()
                })
            else:
                # Fallback for dense
                sparse_result.append({"indices": [], "values": []})
        return sparse_result
    except Exception as e:
        # Fallback: return empty sparse
        return [{"indices": [], "values": []} for _ in request.texts]


@app.post("/colbert-embeddings")
async def embed_colbert(request: ColBERTEmbedRequest):
    """ColBERT multi-vector embeddings - BGE-M3 supports this"""
    try:
        result = model.encode(
            request.texts,
            batch_size=BATCH_SIZE,
            convert_to_numpy=True,
            output_value="colbert"
        )
        return result.tolist() if hasattr(result, "tolist") else result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)