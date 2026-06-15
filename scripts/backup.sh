#!/bin/bash
# =============================================================================
# BACKUP SCRIPT — Full platform backup
# =============================================================================
# Usage: ./backup.sh [tenant_id] [destination]
# =============================================================================

set -euo pipefail

TENANT_ID="${1:-all}"
DESTINATION="${2:-s3://rag-backups/$(date +%Y%m%d-%H%M%S)}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

echo "=== Starting backup at $TIMESTAMP ==="
echo "Tenant: $TENANT_ID"
echo "Destination: $DESTINATION"

# 1. PostgreSQL backup
echo "Backing up PostgreSQL..."
kubectl exec -n rag-platform postgres-0 -- pg_dumpall -U rag | gzip > "/tmp/postgres-${TIMESTAMP}.sql.gz"
mc cp "/tmp/postgres-${TIMESTAMP}.sql.gz" "${DESTINATION}/postgres-${TIMESTAMP}.sql.gz"

# 2. Qdrant snapshot
echo "Backing up Qdrant..."
if [[ "$TENANT_ID" == "all" ]]; then
    COLLECTIONS=$(curl -s http://qdrant.rag-platform.svc.cluster.local:6333/collections | jq -r '.result.collections[].name')
else
    COLLECTIONS="tenant_${TENANT_ID}"
fi

for COLLECTION in $COLLECTIONS; do
    echo "Snapshotting collection: $COLLECTION"
    curl -X POST "http://qdrant.rag-platform.svc.cluster.local:6333/collections/${COLLECTION}/snapshots"
    # Wait for snapshot
    sleep 5
    SNAPSHOT=$(curl -s "http://qdrant.rag-platform.svc.cluster.local:6333/collections/${COLLECTION}/snapshots" | jq -r '.result[-1].name')
    curl -o "/tmp/${COLLECTION}-${SNAPSHOT}" "http://qdrant.rag-platform.svc.cluster.local:6333/collections/${COLLECTION}/snapshots/${SNAPSHOT}"
    mc cp "/tmp/${COLLECTION}-${SNAPSHOT}" "${DESTINATION}/qdrant/${COLLECTION}-${SNAPSHOT}"
done

# 3. MinIO backup (tenant data)
echo "Backing up MinIO..."
if [[ "$TENANT_ID" == "all" ]]; then
    mc mirror --overwrite minio/ "${DESTINATION}/minio/"
else
    mc mirror --overwrite "minio/tenant-${TENANT_ID}/" "${DESTINATION}/minio/tenant-${TENANT_ID}/"
fi

# 4. Redis backup
echo "Backing up Redis..."
kubectl exec -n rag-platform redis-0 -- redis-cli BGSAVE
sleep 10
kubectl cp rag-platform/redis-0:/data/dump.rdb "/tmp/redis-${TIMESTAMP}.rdb"
mc cp "/tmp/redis-${TIMESTAMP}.rdb" "${DESTINATION}/redis-${TIMESTAMP}.rdb"

# 5. Kubernetes resources backup
echo "Backing up Kubernetes resources..."
kubectl get all,configmaps,secrets,pvc,ingress,networkpolicies -n rag-platform -o yaml > "/tmp/k8s-resources-${TIMESTAMP}.yaml"
mc cp "/tmp/k8s-resources-${TIMESTAMP}.yaml" "${DESTINATION}/k8s-resources-${TIMESTAMP}.yaml"

# 6. Tenant-specific resources
if [[ "$TENANT_ID" != "all" ]]; then
    kubectl get all,configmaps,secrets,pvc -n "tenant-${TENANT_ID}" -o yaml > "/tmp/tenant-${TENANT_ID}-${TIMESTAMP}.yaml"
    mc cp "/tmp/tenant-${TENANT_ID}-${TIMESTAMP}.yaml" "${DESTINATION}/tenant-${TENANT_ID}-${TIMESTAMP}.yaml"
fi

# 7. Create backup manifest
cat > "/tmp/backup-manifest-${TIMESTAMP}.json" <<EOF
{
  "timestamp": "${TIMESTAMP}",
  "tenant": "${TENANT_ID}",
  "components": {
    "postgres": "postgres-${TIMESTAMP}.sql.gz",
    "qdrant": ["qdrant/"],
    "minio": "minio/",
    "redis": "redis-${TIMESTAMP}.rdb",
    "k8s": "k8s-resources-${TIMESTAMP}.yaml"
  },
  "version": "1.0.0"
}
EOF
mc cp "/tmp/backup-manifest-${TIMESTAMP}.json" "${DESTINATION}/backup-manifest-${TIMESTAMP}.json"

echo "=== Backup completed: ${DESTINATION} ==="
echo "Manifest: ${DESTINATION}/backup-manifest-${TIMESTAMP}.json"