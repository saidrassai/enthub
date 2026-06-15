#!/bin/bash
# =============================================================================
# RESTORE SCRIPT — Disaster recovery restore
# =============================================================================
# Usage: ./restore.sh <backup_path> [tenant_id]
# Example: ./restore.sh s3://rag-backups/20241215-030000 acme-corp
# =============================================================================

set -euo pipefail

BACKUP_PATH="${1:-}"
TENANT_ID="${2:-all}"

if [[ -z "$BACKUP_PATH" ]]; then
    echo "Usage: $0 <backup_path> [tenant_id]"
    echo "Example: $0 s3://rag-backups/20241215-030000"
    exit 1
fi

echo "=== Restoring from $BACKUP_PATH ==="
echo "Tenant: $TENANT_ID"

# 1. Download manifest
mc cp "${BACKUP_PATH}/backup-manifest-*.json" /tmp/backup-manifest.json
MANIFEST=$(cat /tmp/backup-manifest.json)
BACKUP_TIMESTAMP=$(echo "$MANIFEST" | jq -r '.timestamp')

echo "Backup timestamp: $BACKUP_TIMESTAMP"

# 2. Confirm restore
read -p "This will OVERWRITE current data. Continue? (yes/no): " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
    echo "Aborted"
    exit 1
fi

# 3. Scale down services to prevent writes
echo "Scaling down services..."
kubectl scale deployment rag-api -n rag-platform --replicas=0
kubectl scale deployment langfuse -n rag-platform --replicas=0
kubectl scale statefulset qdrant -n rag-platform --replicas=0

# 4. Restore PostgreSQL
echo "Restoring PostgreSQL..."
mc cp "${BACKUP_PATH}/postgres-${BACKUP_TIMESTAMP}.sql.gz" /tmp/
gunzip -c "/tmp/postgres-${BACKUP_TIMESTAMP}.sql.gz" | kubectl exec -i -n rag-platform postgres-0 -- psql -U rag

# 5. Restore Qdrant
echo "Restoring Qdrant..."
kubectl scale statefulset qdrant -n rag-platform --replicas=1
sleep 30

if [[ "$TENANT_ID" == "all" ]]; then
    for SNAPSHOT in $(mc ls "${BACKUP_PATH}/qdrant/" | awk '{print $NF}'); do
        COLLECTION=$(echo "$SNAPSHOT" | sed 's/-.*//')
        mc cp "${BACKUP_PATH}/qdrant/${SNAPSHOT}" "/tmp/${SNAPSHOT}"
        curl -X POST "http://qdrant.rag-platform.svc.cluster.local:6333/collections/${COLLECTION}/snapshots/upload" \
            -F "snapshot=@/tmp/${SNAPSHOT}"
        curl -X POST "http://qdrant.rag-platform.svc.cluster.local:6333/collections/${COLLECTION}/snapshots/${SNAPSHOT}/recover"
    done
else
    SNAPSHOT=$(mc ls "${BACKUP_PATH}/qdrant/tenant_${TENANT_ID}-*" | awk '{print $NF}' | head -1)
    mc cp "${BACKUP_PATH}/qdrant/${SNAPSHOT}" "/tmp/${SNAPSHOT}"
    curl -X POST "http://qdrant.rag-platform.svc.cluster.local:6333/collections/tenant_${TENANT_ID}/snapshots/upload" \
        -F "snapshot=@/tmp/${SNAPSHOT}"
    curl -X POST "http://qdrant.rag-platform.svc.cluster.local:6333/collections/tenant_${TENANT_ID}/snapshots/${SNAPSHOT}/recover"
fi

# 6. Restore MinIO
echo "Restoring MinIO..."
if [[ "$TENANT_ID" == "all" ]]; then
    mc mirror --overwrite "${BACKUP_PATH}/minio/" minio/
else
    mc mirror --overwrite "${BACKUP_PATH}/minio/tenant-${TENANT_ID}/" "minio/tenant-${TENANT_ID}/"
fi

# 7. Restore Redis
echo "Restoring Redis..."
mc cp "${BACKUP_PATH}/redis-${BACKUP_TIMESTAMP}.rdb" /tmp/
kubectl cp "/tmp/redis-${BACKUP_TIMESTAMP}.rdb" rag-platform/redis-0:/data/dump.rdb
kubectl exec -n rag-platform redis-0 -- redis-cli SHUTDOWN NOSAVE
sleep 5
kubectl delete pod redis-0 -n rag-platform
sleep 10

# 8. Restore Kubernetes resources
echo "Restoring Kubernetes resources..."
kubectl apply -f "${BACKUP_PATH}/k8s-resources-${BACKUP_TIMESTAMP}.yaml"

if [[ "$TENANT_ID" != "all" ]]; then
    kubectl apply -f "${BACKUP_PATH}/tenant-${TENANT_ID}-${BACKUP_TIMESTAMP}.yaml"
fi

# 9. Scale up services
echo "Scaling up services..."
kubectl scale deployment rag-api -n rag-platform --replicas=5
kubectl scale deployment langfuse -n rag-platform --replicas=3

# 10. Verify health
echo "Verifying health..."
sleep 30
curl -f http://rag-api.rag-platform.svc.cluster.local/health
curl -f http://qdrant.rag-platform.svc.cluster.local:6333/health

echo "=== Restore completed successfully ==="
echo "Restored from backup: $BACKUP_TIMESTAMP"