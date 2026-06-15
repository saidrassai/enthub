# =============================================================================
# ENTERPRISE AGENTIC RAG — API SCHEMAS
# =============================================================================

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from enum import Enum


class RetrievalStrategy(str, Enum):
    HYBRID = "hybrid"
    DENSE = "dense"
    SPARSE = "sparse"
    COLBERT = "colbert"


class TenantTier(str, Enum):
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    ONPREM = "onprem"


class GenerationParams(BaseModel):
    """LLM generation parameters"""

    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    top_p: float = Field(default=0.95, ge=0.0, le=1.0)
    top_k: int = Field(default=50, ge=1, le=100)
    max_tokens: int = Field(default=2048, ge=1, le=8192)
    repetition_penalty: float = Field(default=1.1, ge=1.0, le=2.0)
    seed: Optional[int] = None


class QueryRequest(BaseModel):
    """Query request"""

    query: str = Field(..., min_length=1, max_length=4000)
    tenant_id: Optional[str] = None
    session_id: Optional[str] = None
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    retrieval_top_k: int = Field(default=20, ge=1, le=100)
    rerank_top_n: int = Field(default=5, ge=1, le=20)
    generation_params: GenerationParams = Field(default_factory=GenerationParams)
    enable_guardrails: bool = True
    enable_agentic: bool = True
    stream: bool = False


class Citation(BaseModel):
    """Citation in response"""

    document_id: str
    chunk_text: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    """Query response"""

    answer: str
    citations: List[Citation]
    confidence: float
    iterations: int
    guardrails_passed: bool
    guardrails_details: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestionRequest(BaseModel):
    """Document ingestion request"""

    tenant_id: str
    source: str  # s3://, https://, file://, sharepoint://
    content_type: str = "pdf"  # pdf, docx, html, txt, md
    metadata: Dict[str, Any] = Field(default_factory=dict)
    chunk_strategy: str = "semantic"
    chunk_size: int = Field(default=512, ge=100, le=2048)
    chunk_overlap: int = Field(default=50, ge=0, le=512)
    extract_tables: bool = True
    extract_images: bool = False
    generate_summaries: bool = False


class IngestionResponse(BaseModel):
    """Ingestion response"""

    job_id: str
    status: Literal["accepted", "processing", "completed", "failed"]
    message: str
    tenant_id: str
    documents_processed: int = 0
    chunks_created: int = 0
    errors: List[str] = Field(default_factory=list)


class TenantConfig(BaseModel):
    """Tenant configuration"""

    tenant_id: str
    name: str
    tier: TenantTier
    created_at: datetime
    updated_at: datetime

    # Model access
    allowed_models: List[str] = Field(default_factory=list)
    default_llm: str = "Qwen/Qwen2.5-14B-Instruct"
    default_embed: str = "BAAI/bge-m3"
    default_rerank: str = "BAAI/bge-reranker-v2-m3"

    # Limits
    max_qpm: int = 60
    max_storage_gb: int = 10
    max_concurrent_queries: int = 5
    max_context_length: int = 8192

    # Features
    enable_agentic: bool = True
    enable_guardrails: bool = True
    enable_vlm: bool = False
    enable_multimodal: bool = False
    custom_guardrails: List[str] = Field(default_factory=list)

    # Security
    allowed_domains: List[str] = Field(default_factory=list)
    ip_whitelist: List[str] = Field(default_factory=list)
    require_mfa: bool = False

    # Data
    retention_days: int = 365
    backup_enabled: bool = True
    encryption_at_rest: bool = True

    # Integrations
    s3_buckets: List[str] = Field(default_factory=list)
    sharepoint_sites: List[str] = Field(default_factory=list)


class HealthCheck(BaseModel):
    """Health check response"""

    status: Literal["healthy", "degraded", "unhealthy"]
    service: str
    version: str
    timestamp: float
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Error response"""

    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None


# Request/Response examples for OpenAPI
QUERY_EXAMPLE = {
    "query": "What were the Q3 revenue figures and YoY growth drivers?",
    "tenant_id": "acme-corp",
    "retrieval_strategy": "hybrid",
    "retrieval_top_k": 20,
    "rerank_top_n": 5,
    "generation_params": {
        "temperature": 0.1,
        "max_tokens": 2048
    },
    "enable_guardrails": True,
    "enable_agentic": True,
    "stream": False
}

QUERY_RESPONSE_EXAMPLE = {
    "answer": "Based on the Q3 financial report, revenue was $42.3M, representing 18% YoY growth driven by...",
    "citations": [
        {
            "document_id": "doc_123",
            "chunk_text": "Q3 revenue reached $42.3M, up 18% year-over-year...",
            "score": 0.92,
            "metadata": {"page": 3, "section": "Financial Highlights"}
        }
    ],
    "confidence": 0.89,
    "iterations": 2,
    "guardrails_passed": True,
    "guardrails_details": {},
    "metadata": {
        "tenant_id": "acme-corp",
        "model_used": "Qwen/Qwen2.5-14B-Instruct",
        "documents_retrieved": 20,
        "documents_reranked": 5
    }
}