# =============================================================================
# ENTERPRISE AGENTIC RAG — API DEPENDENCIES
# =============================================================================
# Auth, Rate Limiting, Tenant Resolution
# =============================================================================

from typing import Optional, AsyncGenerator
from functools import lru_cache
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt
import redis.asyncio as redis

from ..core.config import Settings, get_settings
from ..core.tenants import TenantManager
from ..agent.graph import create_agent_graph, create_simple_rag_graph
from ..agent.state import RAGState


# -----------------------------------------------------------------------------
# SECURITY SCHEMES
# -----------------------------------------------------------------------------
security = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    """JWT token payload"""
    sub: str  # user_id
    tenant_id: str
    roles: list[str] = []
    exp: int
    iat: int
    email: Optional[str] = None
    name: Optional[str] = None


# -----------------------------------------------------------------------------
# SETTINGS DEPENDENCY
# -----------------------------------------------------------------------------
@lru_cache()
def get_settings() -> Settings:
    return Settings()


# -----------------------------------------------------------------------------
# TENANT RESOLUTION
# -----------------------------------------------------------------------------
async def resolve_tenant(
    request: Request,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security),
    settings: Settings = Depends(get_settings)
) -> str:
    """Resolve tenant ID from header, subdomain, or JWT"""

    # 1. Explicit header (highest priority)
    if x_tenant_id:
        return x_tenant_id

    # 2. JWT token
    if authorization:
        try:
            payload = jwt.decode(
                authorization.credentials,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                audience=settings.JWT_AUDIENCE
            )
            token_data = TokenPayload(**payload)
            return token_data.tenant_id
        except jwt.PyJWTError:
            pass

    # 3. Subdomain (tenant.rag.company.com)
    host = request.headers.get("host", "")
    if "." in host:
        subdomain = host.split(".")[0]
        if subdomain not in ["www", "api", "app", "rag"]:
            return subdomain

    # 4. Path prefix (/tenant/...)
    path = request.url.path
    if path.startswith("/tenant/"):
        return path.split("/")[2]

    # 5. Default from settings
    return settings.DEFAULT_TENANT


async def get_current_tenant(
    tenant_id: str = Depends(resolve_tenant)
) -> str:
    """FastAPI dependency for current tenant"""
    return tenant_id


async def get_optional_tenant(
    tenant_id: Optional[str] = Depends(resolve_tenant)
) -> Optional[str]:
    """Optional tenant (for public endpoints)"""
    return tenant_id


# -----------------------------------------------------------------------------
# TENANT CONFIGURATION
# -----------------------------------------------------------------------------
async def get_tenant_config(
    tenant_id: str = Depends(get_current_tenant),
    settings: Settings = Depends(get_settings)
):
    """Get tenant configuration"""
    tenant_mgr = TenantManager(settings)
    config = await tenant_mgr.get_tenant(tenant_id)
    if not config:
        raise HTTPException(
            status_code=404,
            detail=f"Tenant {tenant_id} not found"
        )
    return config


# -----------------------------------------------------------------------------
# RATE LIMITING
# -----------------------------------------------------------------------------
class RateLimiter:
    """Redis-based sliding window rate limiter"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int = 60
    ) -> tuple[bool, int, int]:
        """
        Returns: (allowed, remaining, reset_time)
        """
        now = int(time.time())
        window_start = now - window

        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window)
        results = await pipe.execute()

        current_count = results[1]
        allowed = current_count < limit
        remaining = max(0, limit - current_count)
        reset_time = now + window

        return allowed, remaining, reset_time


@lru_cache()
def get_redis_client() -> redis.Redis:
    settings = get_settings()
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_redis_client())


async def rate_limit_dependency(
    request: Request,
    tenant_id: str = Depends(get_current_tenant),
    tenant_config = Depends(get_tenant_config),
    limiter: RateLimiter = Depends(get_rate_limiter)
):
    """Rate limiting dependency"""
    # Get limit from tenant config
    limit = tenant_config.max_qpm
    key = f"ratelimit:{tenant_id}:{request.client.host}"

    allowed, remaining, reset_time = await limiter.check_rate_limit(key, limit)

    # Add rate limit headers
    request.state.rate_limit_remaining = remaining
    request.state.rate_limit_reset = reset_time

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_time),
                "Retry-After": str(reset_time - int(time.time()))
            }
        )

    return True


# -----------------------------------------------------------------------------
# API KEY VERIFICATION (for admin endpoints)
# -----------------------------------------------------------------------------
async def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings)
) -> bool:
    """Verify admin API key"""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    # In production, check against hashed keys in DB
    valid_keys = settings.ADMIN_API_KEYS.split(",") if settings.ADMIN_API_KEYS else []
    if x_api_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )

    return True


# -----------------------------------------------------------------------------
# RAG GRAPH FACTORY
# -----------------------------------------------------------------------------
@lru_cache()
def get_rag_graph():
    """Get compiled RAG graph (cached)"""
    settings = get_settings()
    return create_agent_graph(settings)


@lru_cache()
def get_simple_rag_graph():
    """Get simple RAG graph for starter tier"""
    settings = get_settings()
    return create_simple_rag_graph(settings)


# -----------------------------------------------------------------------------
# USER CONTEXT
# -----------------------------------------------------------------------------
async def get_user_context(
    request: Request,
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security),
    settings: Settings = Depends(get_settings)
) -> dict:
    """Extract user context from JWT"""
    if not authorization:
        return {"user_id": "anonymous", "roles": [], "email": None}

    try:
        payload = jwt.decode(
            authorization.credentials,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE
        )
        return {
            "user_id": payload.get("sub"),
            "roles": payload.get("roles", []),
            "email": payload.get("email"),
            "name": payload.get("name"),
        }
    except jwt.PyJWTError:
        return {"user_id": "anonymous", "roles": [], "email": None}


# -----------------------------------------------------------------------------
# DATABASE SESSION
# -----------------------------------------------------------------------------
async def get_db() -> AsyncGenerator:
    """Database session dependency"""
    settings = get_settings()
    # In production: asyncpg pool
    # For now, return None - services handle their own connections
    yield None


# -----------------------------------------------------------------------------
# LANGFUSE CLIENT
# -----------------------------------------------------------------------------
@lru_cache()
def get_langfuse_client():
    """Get Langfuse client for observability"""
    settings = get_settings()
    if not settings.LANGFUSE_PUBLIC_KEY:
        return None

    from langfuse import Langfuse
    return Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST
    )