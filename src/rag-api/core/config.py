# =============================================================================
# ENTERPRISE AGENTIC RAG — CORE CONFIGURATION
# =============================================================================

from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings from environment"""

    # -------------------------------------------------------------------------
    # APPLICATION
    # -------------------------------------------------------------------------
    APP_NAME: str = "Enterprise Agentic RAG"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # development, staging, production
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json, text

    # -------------------------------------------------------------------------
    # NETWORKING
    # -------------------------------------------------------------------------
    DOMAIN: str = "localhost"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4

    # -------------------------------------------------------------------------
    # EXTERNAL SERVICE ENDPOINTS
    # -------------------------------------------------------------------------
    LLM_ENDPOINT: str = "http://llm:8000"
    EMBED_ENDPOINT: str = "http://embed:8000"
    RERANK_ENDPOINT: str = "http://rerank:8000"
    VLM_ENDPOINT: str = "http://vlm:8000"
    PARSE_ENDPOINT: str = "http://parse:8000"
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_API_KEY: Optional[str] = None
    GUARDRAILS_ENDPOINT: str = "http://guardrails:8000"
    KEYCLOAK_URL: str = "http://keycloak:8080"
    KEYCLOAK_REALM: str = "rag-platform"
    KEYCLOAK_CLIENT_ID: str = "rag-api"
    KEYCLOAK_CLIENT_SECRET: str = ""
    LANGFUSE_HOST: str = "http://langfuse:3000"
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    REDIS_URL: str = "redis://redis:6379/0"

    # -------------------------------------------------------------------------
    # DATABASE
    # -------------------------------------------------------------------------
    DATABASE_URL: str = "postgresql://rag:changeme@postgres:5432/rag_platform"
    POSTGRES_PASSWORD: str = "changeme"

    # -------------------------------------------------------------------------
    # MODEL DEFAULTS
    # -------------------------------------------------------------------------
    DEFAULT_LLM_MODEL: str = "Qwen/Qwen2.5-14B-Instruct"
    DEFAULT_EMBED_MODEL: str = "BAAI/bge-m3"
    DEFAULT_RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"
    DEFAULT_VLM_MODEL: str = "Qwen/Qwen2-VL-7B-Instruct"
    DEFAULT_PARSE_MODEL: str = "Marker"

    # Model timeouts
    LLM_TIMEOUT: float = 120.0
    EMBED_TIMEOUT: float = 60.0
    RERANK_TIMEOUT: float = 30.0
    VECTOR_TIMEOUT: float = 30.0
    GUARDRAILS_TIMEOUT: float = 10.0
    PARSE_TIMEOUT: float = 120.0

    # -------------------------------------------------------------------------
    # TENANT DEFAULTS
    # -------------------------------------------------------------------------
    DEFAULT_TENANT: str = "demo"
    TENANT_RESOLUTION: str = "header"  # header, subdomain, path

    # -------------------------------------------------------------------------
    # AUTHENTICATION (JWT)
    # -------------------------------------------------------------------------
    JWT_SECRET_KEY: str = "changeme-generate-with-openssl-rand-base64-32"
    JWT_ALGORITHM: str = "RS256"
    JWT_AUDIENCE: str = "rag-platform"
    JWT_ISSUER: str = "keycloak"
    JWT_PUBLIC_KEY: str = ""  # For RS256 verification

    # Admin API keys (comma-separated)
    ADMIN_API_KEYS: str = ""

    # -------------------------------------------------------------------------
    # FEATURE FLAGS
    # -------------------------------------------------------------------------
    ENABLE_VLM: bool = True
    ENABLE_MULTIMODAL: bool = True
    ENABLE_AGENTIC: bool = True
    ENABLE_GUARDRAILS: bool = True
    ENABLE_CACHING: bool = True
    ENABLE_STREAMING: bool = True

    # -------------------------------------------------------------------------
    # LIMITS
    # -------------------------------------------------------------------------
    MAX_QUERY_LENGTH: int = 4000
    MAX_CONTEXT_LENGTH: int = 8192
    DEFAULT_TOP_K: int = 20
    DEFAULT_RERANK_N: int = 5
    MAX_ITERATIONS: int = 3

    # -------------------------------------------------------------------------
    # CACHING
    # -------------------------------------------------------------------------
    CACHE_TTL: int = 3600  # 1 hour
    CACHE_MAX_SIZE: int = 10000

    # -------------------------------------------------------------------------
    # INGESTION
    # -------------------------------------------------------------------------
    INGESTION_CHUNK_SIZE: int = 512
    INGESTION_CHUNK_OVERLAP: int = 50
    INGESTION_BATCH_SIZE: int = 32

    # -------------------------------------------------------------------------
    # MONITORING
    # -------------------------------------------------------------------------
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    ENABLE_TRACING: bool = True
    TRACE_SAMPLE_RATE: float = 0.1

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# -----------------------------------------------------------------------------
# MODEL REGISTRY
# -----------------------------------------------------------------------------
MODEL_REGISTRY = {
    "llm": {
        "Qwen/Qwen2.5-32B-Instruct": {
            "description": "Best quality, 32B parameters",
            "vram_gb": 18,
            "context_window": 8192,
            "license": "Apache-2.0",
            "tier": ["enterprise", "onprem"]
        },
        "Qwen/Qwen2.5-14B-Instruct": {
            "description": "Best balance, 14B parameters",
            "vram_gb": 8,
            "context_window": 8192,
            "license": "Apache-2.0",
            "tier": ["professional", "enterprise", "onprem"]
        },
        "Qwen/Qwen2.5-7B-Instruct": {
            "description": "Fast, 7B parameters",
            "vram_gb": 4,
            "context_window": 8192,
            "license": "Apache-2.0",
            "tier": ["starter", "professional", "enterprise", "onprem"]
        },
        "meta-llama/Llama-3.1-8B-Instruct": {
            "description": "Meta's Llama 3.1 8B",
            "vram_gb": 6,
            "context_window": 8192,
            "license": "Llama-3.1-Community",
            "tier": ["professional", "enterprise", "onprem"],
            "gated": True
        },
        "google/gemma-2-9b-it": {
            "description": "Google Gemma 2 9B",
            "vram_gb": 6,
            "context_window": 8192,
            "license": "Gemma",
            "tier": ["professional", "enterprise", "onprem"],
            "gated": True
        }
    },
    "embed": {
        "BAAI/bge-m3": {
            "description": "SOTA multilingual dense+sparse+ColBERT",
            "dimensions": 1024,
            "languages": 100,
            "license": "MIT",
            "max_seq_length": 8192
        },
        "nomic-ai/nomic-embed-text-v1.5": {
            "description": "Long context, Apache 2.0",
            "dimensions": 768,
            "license": "Apache-2.0",
            "max_seq_length": 8192
        }
    },
    "rerank": {
        "BAAI/bge-reranker-v2-m3": {
            "description": "SOTA multilingual cross-encoder",
            "languages": 100,
            "license": "MIT",
            "max_seq_length": 512
        }
    },
    "vlm": {
        "Qwen/Qwen2-VL-7B-Instruct": {
            "description": "Best open VLM, 7B",
            "vram_gb": 8,
            "license": "Apache-2.0",
            "max_images": 10,
            "video_support": True
        },
        "Qwen/Qwen2-VL-2B-Instruct": {
            "description": "Lightweight VLM, 2B",
            "vram_gb": 2,
            "license": "Apache-2.0",
            "max_images": 5
        }
    },
    "parse": {
        "Marker": {
            "description": "Best open PDF→Markdown",
            "license": "Apache-2.0",
            "extracts_tables": True,
            "extracts_equations": True,
            "extracts_images": True
        }
    }
}


# -----------------------------------------------------------------------------
# TIER CONFIGURATIONS
# -----------------------------------------------------------------------------
TIER_CONFIGS = {
    "starter": {
        "max_qpm": 60,
        "max_storage_gb": 10,
        "max_concurrent_queries": 5,
        "max_context_length": 4096,
        "enable_agentic": False,
        "enable_guardrails": True,
        "enable_vlm": False,
        "enable_multimodal": False,
        "allowed_models": ["Qwen/Qwen2.5-7B-Instruct"],
        "retention_days": 30,
        "backup_enabled": False,
        "gpu_profile": "shared"
    },
    "professional": {
        "max_qpm": 300,
        "max_storage_gb": 100,
        "max_concurrent_queries": 20,
        "max_context_length": 8192,
        "enable_agentic": True,
        "enable_guardrails": True,
        "enable_vlm": True,
        "enable_multimodal": True,
        "allowed_models": ["Qwen/Qwen2.5-14B-Instruct", "Qwen/Qwen2.5-7B-Instruct"],
        "retention_days": 90,
        "backup_enabled": True,
        "gpu_profile": "mig_1g_10gb"
    },
    "enterprise": {
        "max_qpm": 1000,
        "max_storage_gb": 1000,
        "max_concurrent_queries": 100,
        "max_context_length": 16384,
        "enable_agentic": True,
        "enable_guardrails": True,
        "enable_vlm": True,
        "enable_multimodal": True,
        "allowed_models": ["Qwen/Qwen2.5-32B-Instruct", "Qwen/Qwen2.5-14B-Instruct"],
        "retention_days": 365,
        "backup_enabled": True,
        "gpu_profile": "dedicated_a100_40gb"
    },
    "onprem": {
        "max_qpm": 10000,
        "max_storage_gb": 10000,
        "max_concurrent_queries": 500,
        "max_context_length": 32768,
        "enable_agentic": True,
        "enable_guardrails": True,
        "enable_vlm": True,
        "enable_multimodal": True,
        "allowed_models": ["all"],
        "retention_days": -1,
        "backup_enabled": True,
        "gpu_profile": "customer_defined"
    }
}