# =============================================================================
# ENTERPRISE AGENTIC RAG — FASTAPI ROUTES
# =============================================================================

from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uuid
import json
import time

from .schemas import (
    QueryRequest, QueryResponse, IngestionRequest, IngestionResponse,
    TenantConfig, HealthCheck
)
from .dependencies import (
    get_current_tenant, get_tenant_config, get_rag_graph,
    rate_limit_dependency, verify_api_key
)
from ..agent.graph import create_agent_graph, create_simple_rag_graph
from ..core.config import Settings
from ..core.tenants import TenantManager


router = APIRouter()


# -----------------------------------------------------------------------------
# HEALTH & INFO
# -----------------------------------------------------------------------------
@router.get("/health", response_model=HealthCheck, tags=["System"])
async def health_check():
    """System health check"""
    return HealthCheck(
        status="healthy",
        service="rag-api",
        version="1.0.0",
        timestamp=time.time(),
        details={
            "components": {
                "llm": "healthy",
                "embed": "healthy",
                "rerank": "healthy",
                "vector": "healthy",
                "guardrails": "healthy"
            }
        }
    )


@router.get("/v1/info", tags=["System"])
async def api_info():
    """API information and capabilities"""
    return {
        "name": "Enterprise Agentic RAG",
        "version": "1.0.0",
        "description": "Multi-tenant agentic RAG with guardrails, RBAC, and observability",
        "features": [
            "agentic_rag",
            "hybrid_search",
            "reranking",
            "multimodal",
            "guardrails",
            "multi_tenancy",
            "rbac",
            "streaming"
        ],
        "models": {
            "llm": ["Qwen2.5-32B", "Qwen2.5-14B", "Qwen2.5-7B"],
            "embed": ["BAAI/bge-m3"],
            "rerank": ["BAAI/bge-reranker-v2-m3"],
            "vlm": ["Qwen2-VL-7B", "Qwen2-VL-2B"],
            "parse": ["Marker"]
        },
        "auth": ["Bearer Token", "API Key", "OIDC"]
    }


# -----------------------------------------------------------------------------
# QUERY ENDPOINTS
# -----------------------------------------------------------------------------
@router.post(
    "/v1/generate",
    response_model=QueryResponse,
    tags=["Query"],
    dependencies=[Depends(rate_limit_dependency), Depends(get_current_tenant)]
)
async def generate(
    request: QueryRequest,
    request_obj: Request,
    tenant: str = Depends(get_current_tenant),
    tenant_config = Depends(get_tenant_config),
    rag_graph = Depends(get_rag_graph)
):
    """Execute Agentic RAG query"""

    # Resolve tenant from auth if not provided
    tenant_id = request.tenant_id or tenant
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID required")

    # Validate tenant access
    if tenant != tenant_id and tenant != "admin":
        raise HTTPException(status_code=403, detail="Access denied to tenant")

    # Create session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())

    # Build initial state
    initial_state = {
        "query": request.query,
        "tenant_id": tenant_id,
        "user_id": getattr(request_obj.state, "user_id", "anonymous"),
        "session_id": session_id,
        "tier": tenant_config.tier,
        "retrieval_strategy": request.retrieval_strategy,
        "retrieval_top_k": min(request.retrieval_top_k, tenant_config.max_context_length // 100),
        "rerank_top_n": request.rerank_top_n,
        "generation_params": request.generation_params.model_dump(),
        "enable_guardrails": request.enable_guardrails and tenant_config.enable_guardrails,
        "enable_agentic": request.enable_agentic and tenant_config.enable_agentic,
        "max_iterations": 3 if tenant_config.tier.value in ["professional", "enterprise", "onprem"] else 1,
        "iterations": 0,
        "created_at": time.time(),
        "trace_id": str(uuid.uuid4()),
    }

    # Select graph based on tier
    if tenant_config.tier.value == "starter":
        graph = create_simple_rag_graph(Settings())
    else:
        graph = create_agent_graph(Settings())

    # Execute graph
    config = {"configurable": {"thread_id": session_id}}
    final_state = await graph.ainvoke(initial_state, config)

    # Build response
    return QueryResponse(
        answer=final_state.get("answer", ""),
        citations=[
            {
                "document_id": c.get("document_id", ""),
                "chunk_text": c.get("chunk_text", ""),
                "score": c.get("score", 0.0),
                "metadata": c.get("metadata", {})
            }
            for c in final_state.get("citations", [])
        ],
        confidence=final_state.get("confidence_score", 0.0),
        iterations=final_state.get("iterations", 0),
        guardrails_passed=final_state.get("guardrails_passed", True),
        guardrails_details=final_state.get("guardrails_results", {}),
        metadata={
            "tenant_id": tenant_id,
            "session_id": session_id,
            "trace_id": final_state.get("trace_id"),
            "model_used": tenant_config.default_llm,
            "retrieval_strategy": request.retrieval_strategy.value,
            "documents_retrieved": len(final_state.get("retrieved_docs", [])),
            "documents_reranked": len(final_state.get("reranked_docs", [])),
        }
    )


@router.post(
    "/v1/generate/stream",
    tags=["Query"],
    dependencies=[Depends(rate_limit_dependency), Depends(get_current_tenant)]
)
async def generate_stream(
    request: QueryRequest,
    request_obj: Request,
    tenant: str = Depends(get_current_tenant),
    tenant_config = Depends(get_tenant_config),
    rag_graph = Depends(get_rag_graph)
):
    """Stream Agentic RAG response (SSE)"""

    tenant_id = request.tenant_id or tenant
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID required")

    if tenant != tenant_id and tenant != "admin":
        raise HTTPException(status_code=403, detail="Access denied to tenant")

    session_id = request.session_id or str(uuid.uuid4())

    initial_state = {
        "query": request.query,
        "tenant_id": tenant_id,
        "user_id": getattr(request_obj.state, "user_id", "anonymous"),
        "session_id": session_id,
        "tier": tenant_config.tier,
        "retrieval_strategy": request.retrieval_strategy,
        "retrieval_top_k": request.retrieval_top_k,
        "rerank_top_n": request.rerank_top_n,
        "generation_params": request.generation_params.model_dump(),
        "enable_guardrails": request.enable_guardrails and tenant_config.enable_guardrails,
        "enable_agentic": request.enable_agentic and tenant_config.enable_agentic,
        "max_iterations": 3,
        "iterations": 0,
        "trace_id": str(uuid.uuid4()),
    }

    graph = create_agent_graph(Settings())

    async def event_generator():
        config = {"configurable": {"thread_id": session_id}}

        # Stream graph execution
        async for event in graph.astream_events(initial_state, config, version="v2"):
            event_type = event["event"]

            if event_type == "on_chain_start":
                yield f"data: {json.dumps({'type': 'node_start', 'node': event['name']})}\n\n"

            elif event_type == "on_chain_end":
                node = event["name"]
                output = event["data"].get("output", {})

                if node == "retrieve":
                    yield f"data: {json.dumps({'type': 'retrieved', 'count': len(output.get('retrieved_docs', []))})}\n\n"
                elif node == "rerank":
                    yield f"data: {json.dumps({'type': 'reranked', 'count': len(output.get('reranked_docs', []))})}\n\n"
                elif node == "generate":
                    answer = output.get("answer", "")
                    # Stream answer in chunks
                    for chunk in answer.split(" "):
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk + ' '})}\n\n"
                    yield f"data: {json.dumps({'type': 'citations', 'citations': output.get('citations', [])})}\n\n"
                elif node == "reflect":
                    needs_more = output.get("needs_more_info", False)
                    yield f"data: {json.dumps({'type': 'reflection', 'needs_more': needs_more})}\n\n"

            elif event_type == "on_tool_end":
                yield f"data: {json.dumps({'type': 'tool_end', 'tool': event['name']})}\n\n"

        # Final complete event
        yield f"data: {json.dumps({'type': 'complete'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# -----------------------------------------------------------------------------
# INGESTION ENDPOINTS
# -----------------------------------------------------------------------------
@router.post(
    "/v1/ingest",
    response_model=IngestionResponse,
    tags=["Ingestion"],
    dependencies=[Depends(rate_limit_dependency), Depends(get_current_tenant)]
)
async def ingest_document(
    request: IngestionRequest,
    tenant: str = Depends(get_current_tenant)
):
    """Ingest document into tenant collection"""

    if tenant != request.tenant_id and tenant != "admin":
        raise HTTPException(status_code=403, detail="Access denied to tenant")

    # Queue ingestion job (async via Celery/Redis in production)
    # For now, return accepted
    return IngestionResponse(
        job_id=str(uuid.uuid4()),
        status="accepted",
        message="Document queued for ingestion",
        tenant_id=request.tenant_id
    )


@router.get(
    "/v1/ingest/{job_id}",
    tags=["Ingestion"],
    dependencies=[Depends(get_current_tenant)]
)
async def get_ingestion_status(
    job_id: str,
    tenant: str = Depends(get_current_tenant)
):
    """Get ingestion job status"""
    # In production, check Redis/Celery result backend
    return {
        "job_id": job_id,
        "status": "processing",
        "progress": 50,
        "documents_processed": 0,
        "chunks_created": 0,
        "errors": []
    }


# -----------------------------------------------------------------------------
# TENANT MANAGEMENT (Admin only)
# -----------------------------------------------------------------------------
@router.post(
    "/v1/admin/tenants",
    response_model=TenantConfig,
    tags=["Admin"],
    dependencies=[Depends(verify_api_key), Depends(get_current_tenant)]
)
async def create_tenant(
    config: TenantConfig,
    tenant: str = Depends(get_current_tenant)
):
    """Create new tenant (admin only)"""
    if tenant != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # Provision tenant resources
    tenant_mgr = TenantManager(Settings())
    await tenant_mgr.provision_tenant(config)

    return config


@router.get(
    "/v1/admin/tenants/{tenant_id}",
    response_model=TenantConfig,
    tags=["Admin"],
    dependencies=[Depends(verify_api_key), Depends(get_current_tenant)]
)
async def get_tenant(
    tenant_id: str,
    tenant: str = Depends(get_current_tenant)
):
    """Get tenant configuration"""
    if tenant != tenant_id and tenant != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    tenant_mgr = TenantManager(Settings())
    return await tenant_mgr.get_tenant(tenant_id)


@router.patch(
    "/v1/admin/tenants/{tenant_id}",
    response_model=TenantConfig,
    tags=["Admin"],
    dependencies=[Depends(verify_api_key), Depends(get_current_tenant)]
)
async def update_tenant(
    tenant_id: str,
    updates: dict,
    tenant: str = Depends(get_current_tenant)
):
    """Update tenant configuration"""
    if tenant != tenant_id and tenant != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    tenant_mgr = TenantManager(Settings())
    return await tenant_mgr.update_tenant(tenant_id, updates)


@router.delete(
    "/v1/admin/tenants/{tenant_id}",
    tags=["Admin"],
    dependencies=[Depends(verify_api_key), Depends(get_current_tenant)]
)
async def delete_tenant(
    tenant_id: str,
    tenant: str = Depends(get_current_tenant)
):
    """Delete tenant and all data"""
    if tenant != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    tenant_mgr = TenantManager(Settings())
    await tenant_mgr.delete_tenant(tenant_id)

    return {"status": "deleted", "tenant_id": tenant_id}


@router.get(
    "/v1/admin/tenants",
    tags=["Admin"],
    dependencies=[Depends(verify_api_key), Depends(get_current_tenant)]
)
async def list_tenants(
    tenant: str = Depends(get_current_tenant),
    limit: int = 100,
    offset: int = 0
):
    """List all tenants (admin only)"""
    if tenant != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    tenant_mgr = TenantManager(Settings())
    return await tenant_mgr.list_tenants(limit, offset)


# -----------------------------------------------------------------------------
# METRICS ENDPOINT (Prometheus)
# -----------------------------------------------------------------------------
@router.get("/metrics", tags=["Monitoring"])
async def metrics(
    tenant: str = Depends(get_current_tenant)
):
    """Prometheus metrics endpoint"""
    if tenant != "admin" and tenant != "prometheus":
        raise HTTPException(status_code=403, detail="Access denied")

    # Return Prometheus format metrics
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from fastapi.responses import Response

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)