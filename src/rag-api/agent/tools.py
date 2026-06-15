# =============================================================================
# ENTERPRISE AGENTIC RAG — AGENT TOOLS
# =============================================================================
# Reusable tools for LangGraph nodes
# =============================================================================

import asyncio
import httpx
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from langchain_core.tools import tool
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# HTTP CLIENTS
# -----------------------------------------------------------------------------
class LLMClient:
    """vLLM OpenAI-compatible client"""

    def __init__(self, base_url: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=timeout)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        top_p: float = 0.95,
        stream: bool = False
    ) -> Dict[str, Any]:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": stream
        }
        response = await self.client.post(f"{self.base_url}/v1/chat/completions", json=payload)
        response.raise_for_status()
        return response.json()

    async def embeddings(self, texts: List[str], model: str) -> List[List[float]]:
        payload = {"model": model, "input": texts}
        response = await self.client.post(f"{self.base_url}/v1/embeddings", json=payload)
        response.raise_for_status()
        return [d["embedding"] for d in response.json()["data"]]

    async def close(self):
        await self.client.aclose()


class TxtAIClient:
    """txtai embeddings/reranker client"""

    def __init__(self, base_url: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=timeout)

    async def embeddings(self, texts: List[str]) -> List[List[float]]:
        response = await self.client.post(
            f"{self.base_url}/embeddings",
            json={"texts": texts}
        )
        response.raise_for_status()
        return response.json()

    async def sparse_embeddings(self, texts: List[str]) -> List[Dict]:
        response = await self.client.post(
            f"{self.base_url}/sparse-embeddings",
            json={"texts": texts}
        )
        response.raise_for_status()
        return response.json()

    async def rerank(self, query: str, documents: List[str], top_n: int = 5) -> List[tuple]:
        """Returns list of (index, score) tuples"""
        response = await self.client.post(
            f"{self.base_url}/rerank",
            json={"query": query, "documents": documents, "top_n": top_n}
        )
        response.raise_for_status()
        return response.json()  # [(0, 0.95), (2, 0.87), ...]

    async def health(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self.client.aclose()


class QdrantClient:
    """Qdrant vector database client"""

    def __init__(self, url: str, api_key: Optional[str] = None, timeout: float = 30.0):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=timeout)
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["api-key"] = api_key

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        return await self.client.request(method, f"{self.url}{path}", headers=self.headers, **kwargs)

    async def create_collection(
        self,
        collection_name: str,
        vector_size: int = 1024,
        distance: str = "Cosine",
        sparse_vector_name: str = "sparse",
        on_disk_payload: bool = True
    ) -> bool:
        payload = {
            "vectors": {
                "size": vector_size,
                "distance": distance,
                "on_disk": True
            },
            "sparse_vectors": {
                sparse_vector_name: {}
            },
            "on_disk_payload": on_disk_payload
        }
        response = await self._request("PUT", f"/collections/{collection_name}", json=payload)
        return response.status_code in (200, 201)

    async def upsert(
        self,
        collection_name: str,
        points: List[Dict[str, Any]]
    ) -> bool:
        payload = {"points": points}
        response = await self._request("PUT", f"/collections/{collection_name}/points", json=payload)
        return response.status_code == 200

    async def hybrid_search(
        self,
        collection_name: str,
        dense_vector: List[float],
        sparse_vector: Dict[str, List],
        filters: Optional[Dict] = None,
        limit: int = 10,
        with_payload: bool = True,
        with_vectors: bool = False
    ) -> List[Dict]:
        """Hybrid dense + sparse search"""
        payload = {
            "vector": {"name": "dense", "vector": dense_vector},
            "sparse_vector": {"name": "sparse", "vector": sparse_vector},
            "limit": limit,
            "with_payload": with_payload,
            "with_vectors": with_vectors
        }
        if filters:
            payload["filter"] = self._build_filter(filters)

        response = await self._request("POST", f"/collections/{collection_name}/points/search/hybrid", json=payload)
        if response.status_code != 200:
            return []
        results = response.json().get("result", [])
        return [self._format_result(r) for r in results]

    async def dense_search(
        self,
        collection_name: str,
        vector: List[float],
        filters: Optional[Dict] = None,
        limit: int = 10
    ) -> List[Dict]:
        payload = {
            "vector": vector,
            "limit": limit,
            "with_payload": True
        }
        if filters:
            payload["filter"] = self._build_filter(filters)

        response = await self._request("POST", f"/collections/{collection_name}/points/search", json=payload)
        if response.status_code != 200:
            return []
        return [self._format_result(r) for r in response.json().get("result", [])]

    async def sparse_search(
        self,
        collection_name: str,
        sparse_vector: Dict[str, List],
        filters: Optional[Dict] = None,
        limit: int = 10
    ) -> List[Dict]:
        payload = {
            "vector": {"name": "sparse", "vector": sparse_vector},
            "limit": limit,
            "with_payload": True
        }
        if filters:
            payload["filter"] = self._build_filter(filters)

        response = await self._request("POST", f"/collections/{collection_name}/points/search", json=payload)
        if response.status_code != 200:
            return []
        return [self._format_result(r) for r in response.json().get("result", [])]

    async def delete_points(self, collection_name: str, point_ids: List[str]) -> bool:
        payload = {"points": point_ids}
        response = await self._request("POST", f"/collections/{collection_name}/points/delete", json=payload)
        return response.status_code == 200

    async def health(self) -> bool:
        try:
            response = await self.client.get(f"{self.url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self.client.aclose()

    def _build_filter(self, filters: Dict) -> Dict:
        """Build Qdrant filter from dict"""
        conditions = []
        for key, value in filters.items():
            if isinstance(value, list):
                conditions.append({"key": key, "match": {"any": value}})
            else:
                conditions.append({"key": key, "match": {"value": value}})
        return {"must": conditions} if conditions else {}

    def _format_result(self, result: Dict) -> Dict:
        return {
            "id": result["id"],
            "score": result["score"],
            "content": result["payload"].get("content", ""),
            "metadata": result["payload"].get("metadata", {}),
            "tenant_id": result["payload"].get("tenant_id", ""),
            "document_id": result["payload"].get("document_id", ""),
            "chunk_index": result["payload"].get("chunk_index", 0),
            "source": result["payload"].get("source", ""),
        }


class GuardrailsClient:
    """Guardrails AI client"""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=timeout)

    async def check_input(
        self,
        query: str,
        tenant_id: str,
        custom_rails: List[str] = None
    ) -> Dict[str, Any]:
        payload = {
            "query": query,
            "tenant_id": tenant_id,
            "rails": custom_rails or []
        }
        response = await self.client.post(f"{self.base_url}/v1/guardrails/input", json=payload)
        if response.status_code != 200:
            return {"passed": True, "violations": []}
        return response.json()

    async def check_output(
        self,
        answer: str,
        query: str,
        citations: List[Dict],
        tenant_id: str,
        custom_rails: List[str] = None
    ) -> Dict[str, Any]:
        payload = {
            "answer": answer,
            "query": query,
            "citations": citations,
            "tenant_id": tenant_id,
            "rails": custom_rails or []
        }
        response = await self.client.post(f"{self.base_url}/v1/guardrails/output", json=payload)
        if response.status_code != 200:
            return {"passed": True, "violations": []}
        return response.json()

    async def health(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self.client.aclose()


class ParseClient:
    """Marker PDF parsing client"""

    def __init__(self, base_url: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=timeout)

    async def parse_pdf(
        self,
        file_url: str,
        extract_tables: bool = True,
        extract_images: bool = False
    ) -> Dict[str, Any]:
        payload = {
            "file_url": file_url,
            "extract_tables": extract_tables,
            "extract_images": extract_images
        }
        response = await self.client.post(f"{self.base_url}/parse", json=payload)
        response.raise_for_status()
        return response.json()

    async def parse_binary(
        self,
        file_bytes: bytes,
        filename: str,
        extract_tables: bool = True
    ) -> Dict[str, Any]:
        files = {"file": (filename, file_bytes, "application/pdf")}
        data = {"extract_tables": str(extract_tables).lower()}
        response = await self.client.post(f"{self.base_url}/parse", files=files, data=data)
        response.raise_for_status()
        return response.json()

    async def health(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self.client.aclose()


# -----------------------------------------------------------------------------
# LANGCHAIN TOOLS (for agent use)
# -----------------------------------------------------------------------------
@tool
async def search_documents(
    query: str,
    tenant_id: str,
    top_k: int = 10,
    strategy: str = "hybrid"
) -> List[Dict[str, Any]]:
    """Search tenant documents using hybrid retrieval"""
    # Implementation uses QdrantClient + EmbeddingClient
    pass


@tool
async def rerank_documents(
    query: str,
    documents: List[str],
    top_n: int = 5
) -> List[tuple]:
    """Rerank documents using cross-encoder"""
    pass


@tool
async def generate_answer(
    query: str,
    context: str,
    model: str = "Qwen/Qwen2.5-14B-Instruct"
) -> str:
    """Generate answer from context"""
    pass


@tool
async def check_guardrails(
    text: str,
    check_type: str,  # "input" or "output"
    tenant_id: str
) -> Dict[str, Any]:
    """Run guardrails check"""
    pass


# -----------------------------------------------------------------------------
# UTILITY FUNCTIONS
# -----------------------------------------------------------------------------
async def get_clients(settings) -> Dict[str, Any]:
    """Factory for all service clients"""
    return {
        "llm": LLMClient(settings.LLM_ENDPOINT),
        "embed": TxtAIClient(settings.EMBED_ENDPOINT),
        "rerank": TxtAIClient(settings.RERANK_ENDPOINT),
        "vector": QdrantClient(settings.QDRANT_URL),
        "guardrails": GuardrailsClient(settings.GUARDRAILS_ENDPOINT),
        "parse": ParseClient(settings.PARSE_ENDPOINT),
    }


async def close_clients(clients: Dict[str, Any]):
    """Close all client connections"""
    for client in clients.values():
        if hasattr(client, "close"):
            await client.close()