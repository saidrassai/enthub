# =============================================================================
# ENTERPRISE AGENTIC RAG — INGESTION PIPELINE
# =============================================================================

import asyncio
import hashlib
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
    SemanticChunker
)
from langchain_community.document_loaders import (
    PyMuPDFLoader,
    UnstructuredFileLoader,
    UnstructuredMarkdownLoader,
    UnstructuredHTMLLoader,
    UnstructuredWordDocumentLoader
)

from ..services import VectorService, EmbeddingService, ParseService
from ..core.config import Settings
from ..core.tenants import TenantManager


@dataclass
class IngestionJob:
    job_id: str
    tenant_id: str
    source: str
    content_type: str
    status: str
    progress: float
    documents_processed: int
    chunks_created: int
    errors: List[str]
    created_at: datetime
    updated_at: datetime


class IngestionPipeline:
    """Document ingestion pipeline with multi-modal support"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.vector = VectorService(settings)
        self.embed = EmbeddingService(settings)
        self.parse = ParseService(settings)
        self.tenant_mgr = TenantManager(settings)

        # Text splitters
        self.splitters = {
            "fixed": RecursiveCharacterTextSplitter(
                chunk_size=settings.INGESTION_CHUNK_SIZE,
                chunk_overlap=settings.INGESTION_CHUNK_OVERLAP,
                separators=["\n\n", "\n", ". ", " ", ""]
            ),
            "markdown": MarkdownHeaderTextSplitter(
                headers_to_split_on=[
                    ("#", "Header 1"),
                    ("##", "Header 2"),
                    ("###", "Header 3"),
                ]
            ),
            "semantic": None  # Initialized lazily with embeddings
        }

    async def ingest(
        self,
        tenant_id: str,
        source: str,
        content_type: str = "pdf",
        metadata: Dict[str, Any] = None,
        chunk_strategy: str = "semantic",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        extract_tables: bool = True,
        extract_images: bool = False,
        generate_summaries: bool = False
    ) -> IngestionJob:
        """Ingest document from source"""

        job_id = str(uuid.uuid4())
        job = IngestionJob(
            job_id=job_id,
            tenant_id=tenant_id,
            source=source,
            content_type=content_type,
            status="processing",
            progress=0.0,
            documents_processed=0,
            chunks_created=0,
            errors=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        try:
            # Load document
            documents = await self._load_document(source, content_type, extract_tables, extract_images)
            job.documents_processed = len(documents)
            job.progress = 0.3
            job.updated_at = datetime.utcnow()

            # Parse with Marker (for PDFs)
            if content_type == "pdf":
                parsed = await self.parse.parse_pdf(source, extract_tables, extract_images)
                # Merge Marker output with loaded documents
                documents = self._merge_parsed_content(documents, parsed)

            # Chunk documents
            chunks = await self._chunk_documents(documents, chunk_strategy, chunk_size, chunk_overlap)
            job.progress = 0.6
            job.updated_at = datetime.utcnow()

            # Generate embeddings
            texts = [chunk["content"] for chunk in chunks]
            dense_embeddings = await self.embed.embed_batch(texts)
            sparse_embeddings = []
            for text in texts:
                sparse = await self.embed.embed_sparse(text)
                sparse_embeddings.append(sparse)

            # Prepare points for Qdrant
            points = []
            for i, (chunk, dense_vec, sparse_vec) in enumerate(zip(chunks, dense_embeddings, sparse_embeddings)):
                doc_id = hashlib.sha256(f"{tenant_id}:{chunk['metadata'].get('document_id', '')}:{i}".encode()).hexdigest()[:16]

                points.append({
                    "id": doc_id,
                    "content": chunk["content"],
                    "dense_vector": dense_vec,
                    "sparse_vector": sparse_vec,
                    "metadata": {
                        **chunk["metadata"],
                        "tenant_id": tenant_id,
                        "chunk_index": i,
                        "document_id": chunk["metadata"].get("document_id", ""),
                        "source": source,
                        "created_at": datetime.utcnow().isoformat()
                    }
                })

            # Store in Qdrant
            await self.vector.upsert_documents(tenant_id, points)
            job.chunks_created = len(points)
            job.progress = 1.0
            job.status = "completed"
            job.updated_at = datetime.utcnow()

        except Exception as e:
            job.status = "failed"
            job.errors.append(str(e))
            job.updated_at = datetime.utcnow()

        return job

    async def _load_document(
        self,
        source: str,
        content_type: str,
        extract_tables: bool,
        extract_images: bool
    ) -> List[Dict[str, Any]]:
        """Load document based on content type and source"""

        # Handle different source types (s3://, https://, file://)
        if source.startswith("s3://"):
            local_path = await self._download_s3(source)
        elif source.startswith(("http://", "https://")):
            local_path = await self._download_http(source)
        else:
            local_path = source

        # Select loader
        loader_map = {
            "pdf": PyMuPDFLoader,
            "md": UnstructuredMarkdownLoader,
            "html": UnstructuredHTMLLoader,
            "docx": UnstructuredWordDocumentLoader,
            "txt": UnstructuredFileLoader,
        }

        loader_cls = loader_map.get(content_type, UnstructuredFileLoader)
        loader = loader_cls(local_path)

        # Load with appropriate parameters
        if content_type == "pdf":
            docs = loader.load()
        else:
            docs = loader.load()

        # Convert to standard format
        documents = []
        for i, doc in enumerate(docs):
            documents.append({
                "content": doc.page_content,
                "metadata": {
                    **doc.metadata,
                    "document_id": doc.metadata.get("source", f"doc_{i}"),
                    "page": doc.metadata.get("page", 0)
                }
            })

        return documents

    async def _download_s3(self, s3_url: str) -> str:
        """Download from S3/MinIO"""
        # Implementation with boto3/minio client
        pass

    async def _download_http(self, url: str) -> str:
        """Download from HTTP"""
        import aiohttp
        import tempfile

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise ValueError(f"Failed to download {url}: {resp.status}")

                with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as f:
                    f.write(await resp.read())
                    return f.name

    def _merge_parsed_content(
        self,
        documents: List[Dict],
        parsed: Dict[str, Any]
    ) -> List[Dict]:
        """Merge Marker parsed content with loaded documents"""
        # Marker returns markdown with tables in | format
        # Merge table content into appropriate pages
        return documents  # Placeholder

    async def _chunk_documents(
        self,
        documents: List[Dict],
        strategy: str,
        chunk_size: int,
        chunk_overlap: int
    ) -> List[Dict]:
        """Chunk documents using specified strategy"""

        splitter = self.splitters.get(strategy)
        if not splitter:
            splitter = self.splitters["fixed"]

        if strategy == "semantic" and self.splitters["semantic"] is None:
            # Initialize semantic chunker with embeddings
            self.splitters["semantic"] = SemanticChunker(
                self.embed,
                breakpoint_threshold_type="percentile",
                breakpoint_threshold_amount=95
            )
            splitter = self.splitters["semantic"]

        all_chunks = []
        for doc in documents:
            texts = splitter.split_text(doc["content"])
            for i, text in enumerate(texts):
                all_chunks.append({
                    "content": text,
                    "metadata": {
                        **doc["metadata"],
                        "chunk_index": i
                    }
                })

        return all_chunks

    async def batch_ingest(
        self,
        tenant_id: str,
        sources: List[str],
        **kwargs
    ) -> List[IngestionJob]:
        """Ingest multiple documents in parallel"""
        semaphore = asyncio.Semaphore(4)  # Limit concurrent ingestions

        async def ingest_one(source: str):
            async with semaphore:
                return await self.ingest(tenant_id, source, **kwargs)

        tasks = [ingest_one(src) for src in sources]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def delete_documents(
        self,
        tenant_id: str,
        document_ids: List[str]
    ) -> bool:
        """Delete documents from vector store"""
        point_ids = [
            hashlib.sha256(f"{tenant_id}:{doc_id}".encode()).hexdigest()[:16]
            for doc_id in document_ids
        ]
        return await self.vector.delete_points(tenant_id, point_ids)