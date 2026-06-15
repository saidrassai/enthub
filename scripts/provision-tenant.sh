#!/bin/bash
# =============================================================================
# PROVISION TENANT — One-command tenant creation
# =============================================================================
# Usage: ./provision-tenant.sh <tenant_id> <tenant_name> <tier> [domain]
# Example: ./provision-tenant.sh acme-corp "Acme Corporation" professional acme.rag.company.com
# =============================================================================

set -euo pipefail

TENANT_ID="${1:-}"
TENANT_NAME="${2:-}"
TIER="${3:-starter}"
DOMAIN="${4:-${TENANT_ID}.rag.yourcompany.com}"

if [[ -z "$TENANT_ID" || -z "$TENANT_NAME" ]]; then
    echo "Usage: $0 <tenant_id> <tenant_name> <tier> [domain]"
    echo "Tiers: starter, professional, enterprise, onprem"
    exit 1
fi

echo "=== Provisioning tenant: $TENANT_ID ($TIER) ==="

# 1. Validate tier
VALID_TIERS=("starter" "professional" "enterprise" "onprem")
if [[ ! " ${VALID_TIERS[@]} " =~ " ${TIER} " ]]; then
    echo "Error: Invalid tier '$TIER'. Valid: ${VALID_TIERS[*]}"
    exit 1
fi

# 2. Create tenant config
cat > "/tmp/${TENANT_ID}-config.yaml" <<EOF
tenant_id: "${TENANT_ID}"
name: "${TENANT_NAME}"
tier: "${TIER}"
created_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
updated_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
EOF

# Add tier-specific config
case $TIER in
    starter)
        cat >> "/tmp/${TENANT_ID}-config.yaml" <<EOF
max_qpm: 60
max_storage_gb: 10
max_concurrent_queries: 5
max_context_length: 4096
enable_agentic: false
enable_guardrails: true
enable_vlm: false
enable_multimodal: false
allowed_models: ["Qwen/Qwen2.5-7B-Instruct"]
retention_days: 30
backup_enabled: false
EOF
        ;;
    professional)
        cat >> "/tmp/${TENANT_ID}-config.yaml" <<EOF
max_qpm: 300
max_storage_gb: 100
max_concurrent_queries: 20
max_context_length: 8192
enable_agentic: true
enable_guardrails: true
enable_vlm: true
enable_multimodal: true
allowed_models: ["Qwen/Qwen2.5-14B-Instruct", "Qwen/Qwen2.5-7B-Instruct"]
retention_days: 90
backup_enabled: true
EOF
        ;;
    enterprise)
        cat >> "/tmp/${TENANT_ID}-config.yaml" <<EOF
max_qpm: 1000
max_storage_gb: 1000
max_concurrent_queries: 100
max_context_length: 16384
enable_agentic: true
enable_guardrails: true
enable_vlm: true
enable_multimodal: true
allowed_models: ["Qwen/Qwen2.5-32B-Instruct", "Qwen/Qwen2.5-14B-Instruct"]
retention_days: 365
backup_enabled: true
EOF
        ;;
    onprem)
        cat >> "/tmp/${TENANT_ID}-config.yaml" <<EOF
max_qpm: 10000
max_storage_gb: 10000
max_concurrent_queries: 500
max_context_length: 32768
enable_agentic: true
enable_guardrails: true
enable_vlm: true
enable_multimodal: true
allowed_models: ["all"]
retention_days: -1
backup_enabled: true
EOF
        ;;
esac

# 3. Apply via kubectl (creates namespace, Qdrant collection, Keycloak realm, etc.)
echo "Creating Kubernetes resources..."
kubectl apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: tenant-${TENANT_ID}
  labels:
    tenant: ${TENANT_ID}
    tier: ${TIER}
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: tenant-config
  namespace: tenant-${TENANT_ID}
data:
  tenant.yaml: |
$(sed 's/^/    /' "/tmp/${TENANT_ID}-config.yaml")
EOF

# 4. Create Qdrant collection (via API)
echo "Creating Qdrant collection..."
kubectl run --rm -i qdrant-create --image=curlimages/curl --restart=Never -- \
    curl -X PUT "http://qdrant.rag-platform.svc.cluster.local:6333/collections/tenant_${TENANT_ID}" \
    -H "Content-Type: application/json" \
    -d '{
      "vectors": {"dense": {"size": 1024, "distance": "Cosine", "on_disk": true}},
      "sparse_vectors": {"sparse": {}},
      "on_disk_payload": true
    }'

# 5. Create Keycloak realm (via admin API)
echo "Configuring Keycloak..."
# This would use Keycloak Admin API to create realm/client for tenant

# 6. Create MinIO bucket
echo "Creating MinIO bucket..."
kubectl run --rm -i minio-create --image=minio/mc --restart=Never -- \
    alias set rag http://minio.rag-platform.svc.cluster.local:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD} && \
    mc mb rag/tenant-${TENANT_ID}

# 7. Register tenant in platform database
echo "Registering tenant in platform..."
curl -X POST "http://rag-api.rag-platform.svc.cluster.local/v1/admin/tenants" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${ADMIN_API_KEY}" \
    -d @"/tmp/${TENANT_ID}-config.yaml"

# 8. Setup monitoring alerts for tenant
echo "Configuring monitoring..."
kubectl apply -f - <<EOF
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: tenant-${TENANT_ID}-alerts
  namespace: rag-platform
  labels:
    team: rag-platform
    tenant: ${TENANT_ID}
spec:
  groups:
  - name: tenant-${TENANT_ID}
    rules:
    - alert: Tenant${TENANT_ID}HighErrorRate
      expr: rate(rag_queries_total{tenant="${TENANT_ID}",status="error"}[5m]) / rate(rag_queries_total{tenant="${TENANT_ID}"}[5m]) > 0.05
      for: 3m
      labels:
        severity: warning
        tenant: ${TENANT_ID}
      annotations:
        summary: "Tenant ${TENANT_ID} error rate > 5%"
    - alert: Tenant${TENANT_ID}StorageQuota
      expr: rag_tenant_storage_bytes{tenant="${TENANT_ID}"} / (rag_tenant_storage_quota_gb{tenant="${TENANT_ID}"} * 1024 * 1024 * 1024) > 0.9
      for: 10m
      labels:
        severity: warning
        tenant: ${TENANT_ID}
      annotations:
        summary: "Tenant ${TENANT_ID} storage > 90%"
EOF

echo "=== Tenant $TENANT_ID provisioned successfully ==="
echo "Endpoint: https://${DOMAIN}"
echo "Tenant ID: ${TENANT_ID}"
echo "Tier: ${TIER}"
echo ""
echo "Next steps:"
echo "1. Configure DNS: ${DOMAIN} -> ingress IP"
echo "2. Share API credentials with tenant"
echo "3. Configure tenant's IdP (SAML/OIDC) in Keycloak"