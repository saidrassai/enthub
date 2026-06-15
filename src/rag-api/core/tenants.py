# =============================================================================
# ENTERPRISE AGENTIC RAG — TENANT MANAGEMENT
# =============================================================================

from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import asyncio

from .config import Settings, TIER_CONFIGS, MODEL_REGISTRY
from ..agent.state import TenantConfig, TenantTier


class TenantManager:
    """Manage tenant lifecycle and configuration"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._tenant_cache: Dict[str, TenantConfig] = {}

    async def get_tenant(self, tenant_id: str) -> Optional[TenantConfig]:
        """Get tenant configuration"""
        if tenant_id in self._tenant_cache:
            return self._tenant_cache[tenant_id]

        # In production: fetch from database
        # For now, return default config based on tier
        tier = await self._get_tenant_tier(tenant_id)
        config = self._build_tenant_config(tenant_id, tier)

        self._tenant_cache[tenant_id] = config
        return config

    async def _get_tenant_tier(self, tenant_id: str) -> TenantTier:
        """Get tenant tier from database"""
        # In production: query database
        # Default to starter for unknown tenants
        if tenant_id == "demo":
            return TenantTier.ENTERPRISE
        return TenantTier.STARTER

    def _build_tenant_config(self, tenant_id: str, tier: TenantTier) -> TenantConfig:
        """Build tenant config from tier template"""
        tier_config = TIER_CONFIGS.get(tier.value, TIER_CONFIGS["starter"])

        return TenantConfig(
            tenant_id=tenant_id,
            name=tenant_id,
            tier=tier,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            max_qpm=tier_config["max_qpm"],
            max_storage_gb=tier_config["max_storage_gb"],
            max_concurrent_queries=tier_config["max_concurrent_queries"],
            max_context_length=tier_config["max_context_length"],
            enable_agentic=tier_config["enable_agentic"],
            enable_guardrails=tier_config["enable_guardrails"],
            enable_vlm=tier_config["enable_vlm"],
            enable_multimodal=tier_config["enable_multimodal"],
            allowed_models=tier_config["allowed_models"],
            retention_days=tier_config["retention_days"],
            backup_enabled=tier_config["backup_enabled"]
        )

    async def provision_tenant(self, config: TenantConfig) -> TenantConfig:
        """Provision new tenant resources"""
        # 1. Create Qdrant collection
        from ..services import VectorService
        vector = VectorService(self.settings)
        await vector.create_tenant_collection(config.tenant_id)

        # 2. Create MinIO bucket
        # await self._create_minio_bucket(config.tenant_id)

        # 3. Create Keycloak realm/client
        # await self._create_keycloak_resources(config)

        # 4. Initialize tenant config in database
        # await self._store_tenant_config(config)

        # 5. Cache config
        self._tenant_cache[config.tenant_id] = config

        return config

    async def update_tenant(self, tenant_id: str, updates: Dict[str, Any]) -> TenantConfig:
        """Update tenant configuration"""
        config = await self.get_tenant(tenant_id)
        if not config:
            raise ValueError(f"Tenant {tenant_id} not found")

        # Apply updates
        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)

        config.updated_at = datetime.utcnow()

        # Persist to database
        # await self._store_tenant_config(config)

        # Update cache
        self._tenant_cache[tenant_id] = config

        return config

    async def delete_tenant(self, tenant_id: str) -> bool:
        """Delete tenant and all associated data"""
        # 1. Delete Qdrant collection
        from ..services import VectorService
        vector = VectorService(self.settings)
        await vector.delete_tenant_data(tenant_id)

        # 2. Delete MinIO bucket
        # await self._delete_minio_bucket(tenant_id)

        # 3. Delete Keycloak resources
        # await self._delete_keycloak_resources(tenant_id)

        # 4. Remove from database
        # await self._delete_tenant_config(tenant_id)

        # 5. Clear cache
        self._tenant_cache.pop(tenant_id, None)

        return True

    async def list_tenants(self, limit: int = 100, offset: int = 0) -> List[TenantConfig]:
        """List all tenants"""
        # In production: query database with pagination
        # For now, return cached tenants
        return list(self._tenant_cache.values())[offset:offset + limit]

    async def check_quota(self, tenant_id: str, resource: str, amount: int = 1) -> bool:
        """Check if tenant has quota for resource"""
        config = await self.get_tenant(tenant_id)
        if not config:
            return False

        # Check storage
        if resource == "storage":
            # Query actual usage from Qdrant/MinIO
            current_usage = await self._get_storage_usage(tenant_id)
            return (current_usage + amount) <= (config.max_storage_gb * 1024 * 1024 * 1024)

        # Check QPM
        if resource == "qpm":
            # Query rate limiter
            current_qpm = await self._get_current_qpm(tenant_id)
            return current_qpm < config.max_qpm

        return True

    async def _get_storage_usage(self, tenant_id: str) -> int:
        """Get tenant storage usage in bytes"""
        # Query Qdrant collection info + MinIO bucket size
        return 0  # Placeholder

    async def _get_current_qpm(self, tenant_id: str) -> int:
        """Get current queries per minute"""
        # Query Redis rate limiter
        return 0  # Placeholder

    def get_model_access(self, tenant_id: str) -> Dict[str, List[str]]:
        """Get models accessible to tenant"""
        config = asyncio.run(self.get_tenant(tenant_id))
        if not config:
            return {"llm": [], "embed": [], "rerank": [], "vlm": []}

        if "all" in config.allowed_models:
            return {
                "llm": list(MODEL_REGISTRY["llm"].keys()),
                "embed": list(MODEL_REGISTRY["embed"].keys()),
                "rerank": list(MODEL_REGISTRY["rerank"].keys()),
                "vlm": list(MODEL_REGISTRY["vlm"].keys())
            }

        # Filter by allowed models
        return {
            "llm": [m for m in config.allowed_models if m in MODEL_REGISTRY["llm"]],
            "embed": [config.default_embed],
            "rerank": [config.default_rerank],
            "vlm": [config.default_vlm] if config.enable_vlm else []
        }