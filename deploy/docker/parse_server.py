#!/usr/bin/env python3
# =============================================================================
# PARSE SERVER — Marker PDF parsing API
# =============================================================================

import os
import tempfile
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from pydantic import BaseModel
import uvicorn
from marker.convert import convert_single_pdf


# Configuration
PORT = int(os.getenv("PORT", "8000"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Marker PDF parser service...")
    yield
    print("Shutting down...")


app = FastAPI(title="Marker PDF Parser", version="1.0.0", lifespan=lifespan)


class ParseResponse(BaseModel):
    markdown: str
    tables: list = []
    equations: list = []
    images: dict = {}
    metadata: dict = {}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "parse"}


@app.post("/parse")
async def parse_pdf(
    file: UploadFile = File(...),
    extract_tables: bool = Form(True),
    extract_images: bool = Form(False)
):
    """Parse PDF file"""
    try:
        # Save uploaded file to temp
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Parse with Marker
        result = convert_single_pdf(tmp_path)
        
        # Clean up
        os.unlink(tmp_path)

        # Extract markdown
        markdown = result[0] if isinstance(result, tuple) else result
        
        # Extract metadata
        metadata = {}
        if len(result) > 1 and isinstance(result[1], dict):
            metadata = result[1]
        elif hasattr(result, 'metadata'):
            metadata = result.metadata

        return ParseResponse(
            markdown=markdown,
            tables=metadata.get("tables", []),
            equations=metadata.get("equations", []),
            images=metadata.get("images", {}),
            metadata=metadata
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/parse")
async def parse_binary(
    file_bytes: bytes,
    filename: str,
    extract_tables: bool = True
):
    """Parse binary PDF data"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        result = convert_single_pdf(tmp_path)
        os.unlink(tmp_path)

        markdown = result[0] if isinstance(result, tuple) else result
        metadata = result[1] if isinstance(result, tuple) and len(result) > 1 else {}

        return {
            "markdown": markdown,
            "tables": metadata.get("tables", []),
            "equations": metadata.get("equations", []),
            "images": metadata.get("images", {}),
            "metadata": metadata
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)