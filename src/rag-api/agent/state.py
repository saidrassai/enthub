# =============================================================================
# ENTERPRISE AGENTIC RAG — CORE STATE DEFINITION
# =============================================================================

from typing import TypedDict, List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class TenantTier(str, Enum):
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    ONPREM = "onprem"


class RetrievalStrategy(str, Enum):
    HYBRID = "hybrid"
    DENSE = "dense"
    SPARSE = "sparse"
    COLBERT = "colbert"


class RAGState(TypedDict):
    """LangGraph state for Agentic RAG workflow"""

    # Request context
    query: str
    tenant_id: str
    user_id: str
    session_id: str
    tier: TenantTier

    # Agentic planning
    plan: Optional[List[str]]
    sub_queries: List[str]
    current_sub_query: Optional[str]

    # Retrieval
    retrieved_docs: List[Dict[str, Any]]
    retrieval_strategy: RetrievalStrategy
    retrieval_top_k: int

    # Reranking
    reranked_docs: List[Dict[str, Any]]
    rerank_top_n: int

    # Generation
    answer: str
    citations: List[Dict[str, Any]]
    generation_params: Dict[str, Any]

    # Reflection & quality
    reflection: Optional[str]
    needs_more_info: bool
    confidence_score: float
    iterations: int
    max_iterations: int

    # Guardrails
    guardrails_results: Dict[str, Any]
    pii_detected: bool
    safety_violations: List[str]

    # Metadata
    created_at: datetime
    updated_at: datetime
    trace_id: str


class Document(BaseModel):
    """Retrieved document with metadata"""

    id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0
    rerank_score: Optional[float] = None

    # Tenant isolation
    tenant_id: str
    collection_name: str

    # Source tracking
    source: str
    chunk_index: int
    document_id: str


class Citation(BaseModel):
    """Answer citation"""

    document_id: str
    chunk_text: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GenerationParams(BaseModel):
    """LLM generation parameters"""

    temperature: float = 0.1
    top_p: float = 0.95
    top_k: int = 50
    max_tokens: int = 2048
    repetition_penalty: float = 1.1
    seed: Optional[int] = None


class QueryRequest(BaseModel):
    """API request schema"""

    query: str = Field(..., min_length=1, max_length=4000)
    tenant_id: Optional[str] = None  # Resolved from auth/header
    session_id: Optional[str] = None
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    retrieval_top_k: int = 20
    rerank_top_n: int = 5
    generation_params: GenerationParams = Field(default_factory=GenerationParams)
    enable_guardrails: bool = True
    enable_agentic: bool = True
    stream: bool = False


class QueryResponse(BaseModel):
    """API response schema"""

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
    content_type: str  # pdf, docx, html, txt, md
    metadata: Dict[str, Any] = Field(default_factory=dict)
    chunk_strategy: str = "semantic"  # semantic, fixed, recursive
    chunk_size: int = 512
    chunk_overlap: int = 50
    extract_tables: bool = True
    extract_images: bool = False
    generate_summaries: bool = False


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
    """Service health status"""

    status: Literal["healthy", "degraded", "unhealthy"]
    service: str
    version: str
    timestamp: datetime
    details: Dict[str, Any] = Field(default_factory=dict)