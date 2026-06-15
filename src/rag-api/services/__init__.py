# =============================================================================
# ENTERPRISE AGENTIC RAG — SERVICE CLIENTS
# =============================================================================

import httpx
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ..core.config import Settings


# -----------------------------------------------------------------------------
# LLM SERVICE (vLLM OpenAI-compatible)
# -----------------------------------------------------------------------------
class LLMService:
    """vLLM chat completion client"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.LLM_ENDPOINT.rstrip("/") + "/v1"
        self.client = httpx.AsyncClient(timeout=settings.LLM_TIMEOUT)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        top_p: float = 0.95,
        stream: bool = False
    ) -> Any:
        """Chat completion"""
        payload = {
            "model": model or self.settings.DEFAULT_LLM_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": stream
        }
        response = await self.client.post(f"{self.base_url}/chat/completions", json=payload)
        response.raise_for_status()

        if stream:
            return response.aiter_lines()

        return response.json()

    async def embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> List[List[float]]:
        """Generate embeddings (if model supports)"""
        payload = {
            "model": model or self.settings.DEFAULT_EMBED_MODEL,
            "input": texts
        }
        response = await self.client.post(f"{self.base_url}/embeddings", json=payload)
        response.raise_for_status()
        return [d["embedding"] for d in response.json()["data"]]

    async def health(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/models")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self.client.aclose()


# -----------------------------------------------------------------------------
# EMBEDDING SERVICE (txtai - BGE-M3)
# -----------------------------------------------------------------------------
class EmbeddingService:
    """txtai embeddings client (dense + sparse + ColBERT)"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.EMBED_ENDPOINT.rstrip("/")
        self.client = httpx.AsyncClient(timeout=settings.EMBED_TIMEOUT)

    async def embed_dense(self, text: str) -> List[float]:
        """Dense vector embedding"""
        response = await self.client.post(
            f"{self.base_url}/embeddings",
            json={"texts": [text]}
        )
        response.raise_for_status()
        return response.json()[0]

    async def embed_sparse(self, text: str) -> Dict[str, List]:
        """Sparse vector embedding (BM25-style)"""
        response = await self.client.post(
            f"{self.base_url}/sparse-embeddings",
            json={"texts": [text]}
        )
        response.raise_for_status()
        result = response.json()[0]
        return {"indices": result["indices"], "values": result["values"]}

    async def embed_colbert(self, text: str) -> List[List[float]]:
        """ColBERT multi-vector embedding"""
        response = await self.client.post(
            f"{self.base_url}/colbert-embeddings",
            json={"texts": [text]}
        )
        response.raise_for_status()
        return response.json()[0]

    async def embed_hybrid(self, text: str) -> tuple[List[float], Dict]:
        """Get both dense and sparse embeddings"""
        dense = await self.embed_dense(text)
        sparse = await self.embed_sparse(text)
        return dense, sparse

    async def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32
    ) -> List[List[float]]:
        """Batch embedding"""
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = await self.client.post(
                f"{self.base_url}/embeddings",
                json={"texts": batch}
            )
            response.raise_for_status()
            all_embeddings.extend(response.json())
        return all_embeddings

    async def health(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self.client.aclose()


# -----------------------------------------------------------------------------
# RERANKER SERVICE (txtai - BGE-Reranker-v2-M3)
# -----------------------------------------------------------------------------
class RerankService:
    """Cross-encoder reranker client"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.RERANK_ENDPOINT.rstrip("/")
        self.client = httpx.AsyncClient(timeout=settings.RERANK_TIMEOUT)

    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_n: int = 5
    ) -> List[tuple]:
        """Rerank documents, returns list of (index, score)"""
        response = await self.client.post(
            f"{self.base_url}/rerank",
            json={"query": query, "documents": documents, "top_n": top_n}
        )
        response.raise_for_status()
        return response.json()  # [(0, 0.95), (2, 0.87), ...]

    async def rerank_with_scores(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """Rerank documents with full metadata"""
        texts = [d.get("content", "") for d in documents]
        ranked = await self.rerank(query, texts, top_n)

        results = []
        for idx, score in ranked:
            doc = documents[idx].copy()
            doc["rerank_score"] = score
            results.append(doc)
        return results

    async def health(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self.client.aclose()


# -----------------------------------------------------------------------------
# VECTOR DATABASE SERVICE (Qdrant)
# -----------------------------------------------------------------------------
class VectorService:
    """Qdrant vector database client"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.url = settings.QDRANT_URL.rstrip("/")
        self.api_key = settings.QDRANT_API_KEY
        self.client = httpx.AsyncClient(timeout=settings.VECTOR_TIMEOUT)
        self.headers = {"Content-Type": "application/json"}
        if self.api_key:
            self.headers["api-key"] = self.api_key

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        return await self.client.request(
            method, f"{self.url}{path}", headers=self.headers, **kwargs
        )

    async def create_tenant_collection(
        self,
        tenant_id: str,
        vector_size: int = 1024,
        distance: str = "Cosine"
    ) -> bool:
        """Create collection for tenant with hybrid search config"""
        collection_name = f"tenant_{tenant_id}"

        payload = {
            "vectors": {
                "dense": {
                    "size": vector_size,
                    "distance": distance,
                    "on_disk": True
                }
            },
            "sparse_vectors": {
                "sparse": {}
            },
            "on_disk_payload": True,
            "hnsw_config": {
                "m": 16,
                "ef_construct": 100,
                "full_scan_threshold": 10000
            },
            "quantization_config": {
                "scalar": {
                    "type": "int8",
                    "quantile": 0.99,
                    "always_ram": True
                }
            }
        }

        response = await self._request("PUT", f"/collections/{collection_name}", json=payload)
        return response.status_code in (200, 201)

    async def upsert_documents(
        self,
        tenant_id: str,
        documents: List[Dict[str, Any]]
    ) -> bool:
        """Upsert documents to tenant collection"""
        collection_name = f"tenant_{tenant_id}"

        points = []
        for doc in documents:
            points.append({
                "id": doc["id"],
                "vector": {
                    "dense": doc["dense_vector"],
                    "sparse": doc.get("sparse_vector", {"indices": [], "values": []})
                },
                "payload": {
                    "content": doc["content"],
                    "metadata": doc.get("metadata", {}),
                    "tenant_id": tenant_id,
                    "document_id": doc.get("document_id", ""),
                    "chunk_index": doc.get("chunk_index", 0),
                    "source": doc.get("source", ""),
                    "created_at": doc.get("created_at", "")
                }
            })

        payload = {"points": points}
        response = await self._request("PUT", f"/collections/{collection_name}/points", json=payload)
        return response.status_code == 200

    async def hybrid_search(
        self,
        tenant_id: str,
        dense_vector: List[float],
        sparse_vector: Dict[str, List],
        filters: Optional[Dict] = None,
        limit: int = 10,
        with_payload: bool = True
    ) -> List[Dict]:
        """Hybrid dense + sparse search"""
        collection_name = f"tenant_{tenant_id}"

        payload = {
            "vector": {"name": "dense", "vector": dense_vector},
            "sparse_vector": {"name": "sparse", "vector": sparse_vector},
            "limit": limit,
            "with_payload": with_payload,
            "with_vectors": False
        }
        if filters:
            payload["filter"] = self._build_filter(filters)

        response = await self._request("POST", f"/collections/{collection_name}/points/search/hybrid", json=payload)
        if response.status_code != 200:
            return []
        return [self._format_result(r) for r in response.json().get("result", [])]

    async def dense_search(
        self,
        tenant_id: str,
        vector: List[float],
        filters: Optional[Dict] = None,
        limit: int = 10
    ) -> List[Dict]:
        collection_name = f"tenant_{tenant_id}"
        payload = {"vector": vector, "limit": limit, "with_payload": True}
        if filters:
            payload["filter"] = self._build_filter(filters)

        response = await self._request("POST", f"/collections/{collection_name}/points/search", json=payload)
        if response.status_code != 200:
            return []
        return [self._format_result(r) for r in response.json().get("result", [])]

    async def get_collection_info(self, tenant_id: str) -> Dict:
        """Get collection stats"""
        collection_name = f"tenant_{tenant_id}"
        response = await self._request("GET", f"/collections/{collection_name}")
        if response.status_code != 200:
            return {}
        return response.json().get("result", {})

    async def delete_tenant_data(self, tenant_id: str) -> bool:
        """Delete all tenant data"""
        collection_name = f"tenant_{tenant_id}"
        response = await self._request("DELETE", f"/collections/{collection_name}")
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


# -----------------------------------------------------------------------------
# GUARDRAILS SERVICE
# -----------------------------------------------------------------------------
class GuardrailsService:
    """Guardrails AI client"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.GUARDRAILS_ENDPOINT.rstrip("/")
        self.client = httpx.AsyncClient(timeout=settings.GUARDRAILS_TIMEOUT)

    async def check_input(
        self,
        query: str,
        tenant_id: str,
        custom_rails: List[str] = None
    ) -> Dict[str, Any]:
        payload = {
            "text": query,
            "tenant_id": tenant_id,
            "rails": custom_rails or []
        }
        response = await self.client.post(f"{self.base_url}/v1/guard", json=payload)
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
            "text": answer,
            "query": query,
            "citations": citations,
            "tenant_id": tenant_id,
            "rails": custom_rails or []
        }
        response = await self.client.post(f"{self.base_url}/v1/guard", json=payload)
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


# -----------------------------------------------------------------------------
# PARSE SERVICE (Marker)
# -----------------------------------------------------------------------------
class ParseService:
    """Marker PDF parsing client"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.PARSE_ENDPOINT.rstrip("/")
        self.client = httpx.AsyncClient(timeout=settings.PARSE_TIMEOUT)

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
# SERVICE REGISTRY
# -----------------------------------------------------------------------------
@dataclass
class ServiceClients:
    llm: LLMService
    embed: EmbeddingService
    rerank: RerankService
    vector: VectorService
    guardrails: GuardrailsService
    parse: ParseService


async def create_service_clients(settings: Settings) -> ServiceClients:
    return ServiceClients(
        llm=LLMService(settings),
        embed=EmbeddingService(settings),
        rerank=RerankService(settings),
        vector=VectorService(settings),
        guardrails=GuardrailsService(settings),
        parse=ParseService(settings)
    )


async def close_service_clients(clients: ServiceClients):
    await clients.llm.close()
    await clients.embed.close()
    await clients.rerank.close()
    await clients.vector.close()
    await clients.guardrails.close()
    await clients.parse.close()