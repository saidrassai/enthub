#!/bin/bash
# =============================================================================
# UPDATE MODELS — Rolling model updates with zero downtime
# =============================================================================
# Usage: ./update-models.sh <model_name> <new_version>
# Example: ./update-models.sh Qwen/Qwen2.5-14B-Instruct v1.1
# =============================================================================

set -euo pipefail

MODEL_NAME="${1:-}"
NEW_TAG="${2:-latest}"

if [[ -z "$MODEL_NAME" ]]; then
    echo "Usage: $0 <model_name> [tag]"
    echo "Example: $0 Qwen/Qwen2.5-14B-Instruct v1.1"
    exit 1
fi

echo "=== Updating model: $MODEL_NAME to $NEW_TAG ==="

# 1. Pull new model image
echo "Pulling new vLLM image..."
docker pull vllm/vllm-openai:${NEW_TAG}

# 2. Create new deployment with updated model
NEW_DEPLOYMENT="vllm-llm-$(date +%s)"
kubectl get deployment vllm-llm -n rag-platform -o yaml | \
    sed "s/name: vllm-llm/name: ${NEW_DEPLOYMENT}/" | \
    sed "s/vllm\/vllm-openai:.*/vllm\/vllm-openai:${NEW_TAG}/" | \
    sed "s/model: .*/model: ${MODEL_NAME}/" | \
    kubectl apply -f -

# 3. Wait for new deployment to be ready
echo "Waiting for new deployment to be ready..."
kubectl rollout status deployment/${NEW_DEPLOYMENT} -n rag-platform --timeout=300s

# 4. Run health checks on new deployment
echo "Running health checks..."
NEW_POD=$(kubectl get pods -n rag-platform -l app=${NEW_DEPLOYMENT} -o jsonpath='{.items[0].metadata.name}')
kubectl wait --for=condition=ready pod/${NEW_POD} -n rag-platform --timeout=120s

# Test the new model
HEALTH=$(kubectl exec -n rag-platform ${NEW_POD} -- curl -s http://localhost:8000/health)
if [[ "$HEALTH" != *"healthy"* ]]; then
    echo "Health check failed, rolling back..."
    kubectl delete deployment ${NEW_DEPLOYMENT} -n rag-platform
    exit 1
fi

# 5. Run smoke tests
echo "Running smoke tests..."
SMOKE_RESULT=$(kubectl exec -n rag-platform ${NEW_POD} -- curl -s -X POST http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model": "'${MODEL_NAME}'", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 10}')

if [[ "$SMOKE_RESULT" == *"error"* ]]; then
    echo "Smoke test failed, rolling back..."
    kubectl delete deployment ${NEW_DEPLOYMENT} -n rag-platform
    exit 1
fi

# 6. Switch service to new deployment (canary)
echo "Switching traffic to new deployment (canary 10%)..."
kubectl patch service vllm-llm -n rag-platform -p '{"spec":{"selector":{"app": "'${NEW_DEPLOYMENT}'"}}}'

# 7. Monitor for 5 minutes
echo "Monitoring canary for 5 minutes..."
sleep 300

ERROR_RATE=$(kubectl exec -n rag-platform prometheus-0 -- promtool query instant 'rate(rag_queries_total{status="error"}[5m]) / rate(rag_queries_total[5m])' | tail -1)

if (( $(echo "$ERROR_RATE > 0.05" | bc -l) )); then
    echo "Error rate too high (${ERROR_RATE}), rolling back..."
    kubectl patch service vllm-llm -n rag-platform -p '{"spec":{"selector":{"app": "vllm-llm"}}}'
    kubectl delete deployment ${NEW_DEPLOYMENT} -n rag-platform
    exit 1
fi

# 8. Full switch
echo "Canary successful, switching 100% traffic..."
kubectl patch service vllm-llm -n rag-platform -p '{"spec":{"selector":{"app": "'${NEW_DEPLOYMENT}'"}}}'

# 9. Clean up old deployment
kubectl delete deployment vllm-llm -n rag-platform
kubectl rename deployment ${NEW_DEPLOYMENT} vllm-llm -n rag-platform

# 10. Update ConfigMap
kubectl patch configmap rag-config -n rag-platform -p '{"data":{"LLM_MODEL": "'${MODEL_NAME}'"}}'

echo "=== Model updated successfully ==="
echo "New model: ${MODEL_NAME}:${NEW_TAG}"

# 11. Notify monitoring
curl -X POST http://alertmanager.rag-platform.svc.cluster.local:9093/api/v1/alerts \
    -H "Content-Type: application/json" \
    -d '[{"labels":{"alertname":"ModelUpdated","model":"'${MODEL_NAME}'","version":"'${NEW_TAG}'"},"annotations":{"summary":"Model updated to '${MODEL_NAME}:${NEW_TAG}'"}}]'