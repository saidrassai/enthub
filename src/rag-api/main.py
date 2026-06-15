# =============================================================================
# ENTERPRISE AGENTIC RAG — MAIN APPLICATION
# =============================================================================

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import uvicorn
import logging
import sys

from .core.config import get_settings
from .core.tenants import TenantManager
from .services import create_service_clients, close_service_clients, ServiceClients
from .api.routes import router as api_router
from .api.dependencies import get_langfuse_client

# -----------------------------------------------------------------------------
# METRICS
# -----------------------------------------------------------------------------
QUERY_COUNTER = Counter("rag_queries_total", "Total queries", ["tenant", "status"])
QUERY_LATENCY = Histogram("rag_query_latency_seconds", "Query latency", ["tenant"])
INGESTION_COUNTER = Counter("rag_ingestions_total", "Total ingestions", ["tenant", "status"])
ACTIVE_TENANTS = Counter("rag_active_tenants", "Active tenants")


# -----------------------------------------------------------------------------
# LIFESPAN
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    settings = get_settings()

    # Startup
    logging.info("Starting Enterprise Agentic RAG...")

    # Initialize service clients
    app.state.services = await create_service_clients(settings)
    logging.info("Service clients initialized")

    # Initialize tenant manager
    app.state.tenant_manager = TenantManager(settings)
    logging.info("Tenant manager initialized")

    # Initialize Langfuse
    app.state.langfuse = get_langfuse_client()
    if app.state.langfuse:
        logging.info("Langfuse observability enabled")

    # Verify service health
    health_checks = await asyncio.gather(
        app.state.services.llm.health(),
        app.state.services.embed.health(),
        app.state.services.rerank.health(),
        app.state.services.vector.health(),
        app.state.services.guardrails.health(),
        app.state.services.parse.health(),
        return_exceptions=True
    )

    services = ["llm", "embed", "rerank", "vector", "guardrails", "parse"]
    for svc, healthy in zip(services, health_checks):
        if isinstance(healthy, Exception) or not healthy:
            logging.warning(f"Service {svc} health check failed: {healthy}")
        else:
            logging.info(f"Service {svc} healthy")

    logging.info("Startup complete")

    yield

    # Shutdown
    logging.info("Shutting down...")
    await close_service_clients(app.state.services)
    logging.info("Shutdown complete")


# -----------------------------------------------------------------------------
# APPLICATION FACTORY
# -----------------------------------------------------------------------------
def create_app() -> FastAPI:
    settings = get_settings()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    if settings.LOG_FORMAT == "json":
        import json_logging
        json_logging.init_fastapi(enable_json=True)
        json_logging.init_request_instrument(app)

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Multi-tenant Agentic RAG with Guardrails, RBAC, and Observability",
        lifespan=lifespan,
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    )

    # -------------------------------------------------------------------------
    # MIDDLEWARE
    # -------------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS.split(",") if hasattr(settings, "CORS_ORIGINS") else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # -------------------------------------------------------------------------
    # REQUEST PROCESSING
    # -------------------------------------------------------------------------
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        import time
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    @app.middleware("http")
    async def add_rate_limit_headers(request: Request, call_next):
        response = await call_next(request)
        if hasattr(request.state, "rate_limit_remaining"):
            response.headers["X-RateLimit-Remaining"] = str(request.state.rate_limit_remaining)
            response.headers["X-RateLimit-Reset"] = str(request.state.rate_limit_reset)
        return response

    @app.middleware("http")
    async def tenant_context_middleware(request: Request, call_next):
        """Extract and inject tenant context"""
        from .api.dependencies import resolve_tenant
        try:
            tenant_id = await resolve_tenant(request)
            request.state.tenant_id = tenant_id
        except Exception:
            request.state.tenant_id = get_settings().DEFAULT_TENANT
        return await call_next(request)

    # -------------------------------------------------------------------------
    # EXCEPTION HANDLERS
    # -------------------------------------------------------------------------
    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return JSONResponse(
            status_code=404,
            content={"error": "Not Found", "message": str(exc)}
        )

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc):
        logging.error(f"Internal error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal Server Error", "message": "An unexpected error occurred"}
        )

    # -------------------------------------------------------------------------
    # ROUTES
    # -------------------------------------------------------------------------
    app.include_router(api_router, prefix="")

    # -------------------------------------------------------------------------
    # METRICS ENDPOINT
    # -------------------------------------------------------------------------
    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # -------------------------------------------------------------------------
    # ROOT
    # -------------------------------------------------------------------------
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running",
            "docs": "/docs",
            "health": "/health"
        }

    return app


# -----------------------------------------------------------------------------
# ENTRY POINT
# -----------------------------------------------------------------------------
app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        workers=settings.API_WORKERS if settings.ENVIRONMENT == "production" else 1,
        reload=settings.ENVIRONMENT == "development",
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )