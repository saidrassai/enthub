# Enterprise Agentic RAG — Troubleshooting Guide

## Quick Reference

| Symptom | Likely Cause | First Check |
|---------|--------------|-------------|
| High latency (>30s) | vLLM queue full, GPU OOM | `kubectl logs vllm-llm`, `nvidia-smi` |
| 500 errors | Service unavailable, timeout | `kubectl get pods`, service health endpoints |
| No results | Qdrant empty, wrong tenant | `curl qdrant:6333/collections`, check tenant_id |
| Guardrails blocking | PII detected, safety violation | Check guardrails logs, adjust rails |
| Auth failures | Token expired, wrong audience | Check Keycloak logs, JWT config |
| Ingestion stuck | Marker OOM, large PDF | Check parse logs, split files |
| GPU not detected | Driver issue, wrong runtime | `nvidia-smi`, `kubectl describe node` |

---

## Component-Specific Troubleshooting

### 1. vLLM (LLM Inference)

#### High Latency / Timeouts

**Symptoms**: Query takes >30s, client timeouts

**Diagnosis**:
```bash
# Check vLLM metrics
curl http://vllm-llm:8000/metrics | grep -E "queue|pending|running|gpu"

# Key metrics:
# vllm_request_queue_depth - should be <10
# vllm_gpu_memory_used_bytes / vllm_gpu_memory_total_bytes - should be <0.9
# vllm_avg_request_latency_seconds - P99 should be <30s
```

**Causes & Fixes**:
| Cause | Fix |
|-------|-----|
| Queue depth > 50 | Scale vLLM replicas, reduce `max_concurrent_queries` per tenant |
| GPU memory > 95% | Reduce `gpu_memory_utilization`, enable quantization, smaller model |
| Long context | Reduce `max_model_len`, enable chunked prefill |
| Cold start | Keep minimum replicas warm, use `--enforce-eager` for faster startup |

#### Out of Memory (OOM)

**Symptoms**: Pod crashes, `OOMKilled`, `CUDA out of memory`

**Diagnosis**:
```bash
kubectl describe pod vllm-llm-xxx | grep -A5 "OOMKilled"
nvidia-smi  # Check memory usage
```

**Fixes**:
```yaml
# Reduce GPU memory utilization
vllm:
  gpu_memory_utilization: 0.80  # was 0.85
  max_model_len: 4096  # was 8192
  quantization: fp8  # Enable FP8 quantization
  tensor_parallel_size: 2  # If multi-GPU available
```

#### Model Not Loading

**Symptoms**: `/health` fails, model not in `/v1/models`

**Diagnosis**:
```bash
kubectl logs vllm-llm-xxx -f
# Look for: "Loading model", "Downloading weights", HF_TOKEN errors
```

**Fixes**:
- Check `HF_TOKEN` secret exists and is valid
- Verify model name in config
- Check disk space for model cache (`df -h /root/.cache`)
- Increase `initialDelaySeconds` for liveness probe

### 2. Qdrant (Vector Database)

#### Slow Queries

**Symptoms**: Search takes >5s

**Diagnosis**:
```bash
curl http://qdrant:6333/collections/tenant_xxx | jq '.result.config.hnsw_config'
curl http://qdrant:6333/metrics | grep -E "search|latency"
```

**Fixes**:
```yaml
# Optimize HNSW
collection_config:
  hnsw_config:
    m: 16  # Reduce from 32
    ef_construct: 100  # Reduce from 200
  quantization:
    scalar:
      type: int8  # Enable quantization
      quantile: 0.99
```

#### Collection Not Found

**Symptoms**: `404 Collection not found`, tenant can't query

**Diagnosis**:
```bash
curl http://qdrant:6333/collections
# Check if collection exists: tenant_<tenant_id>
```

**Fixes**:
```bash
# Provision collection
curl -X PUT http://qdrant:6333/collections/tenant_acme-corp \
  -H "Content-Type: application/json" \
  -d '{"vectors": {"dense": {"size": 1024, "distance": "Cosine"}}, "sparse_vectors": {"sparse": {}}, "on_disk_payload": true}'
```

#### Disk Full

**Symptoms**: Writes fail, `No space left on device`

**Diagnosis**:
```bash
kubectl exec qdrant-0 -- df -h /qdrant/storage
```

**Fixes**:
- Expand PVC: `kubectl patch pvc qdrant-storage-qdrant-0 -p '{"spec":{"resources":{"requests":{"storage":"500Gi"}}}}`
- Enable quantization (reduces 4x)
- Delete old collections
- Enable `on_disk_payload: true`

### 3. txtai (Embeddings / Reranker)

#### Slow Embeddings

**Symptoms**: Ingestion slow, embedding endpoint timeout

**Diagnosis**:
```bash
curl http://embed:8000/metrics | grep -E "latency|batch"
```

**Fixes**:
- Batch embeddings: `batch_size: 64` (was 32)
- Increase replicas: `replicas: 3`
- Move to GPU if on CPU: `device: cuda`

#### Reranker Poor Quality

**Symptoms**: Irrelevant results at top

**Diagnosis**:
```bash
# Test reranker directly
curl -X POST http://rerank:8000/rerank \
  -d '{"query": "test", "documents": ["doc1", "doc2"], "top_n": 2}'
```

**Fixes**:
- Verify model: `BAAI/bge-reranker-v2-m3`
- Check max sequence length (512 tokens)
- Increase `top_n` from retrieval (20→50)

### 4. Marker (PDF Parsing)

#### OOM on Large PDFs

**Symptoms**: Parse pod crashes, `MemoryError`

**Diagnosis**:
```bash
kubectl logs parse-xxx | grep -i memory
```

**Fixes**:
```yaml
# Increase memory limit
parse:
  resources:
    limits:
      memory: 8Gi  # was 4Gi
  # Or split PDF before parsing
```

#### Slow Parsing

**Symptoms**: Ingestion takes minutes per PDF

**Diagnosis**:
```bash
kubectl logs parse-xxx | grep -E "pages|tables|time"
```

**Fixes**:
- Disable table extraction if not needed: `extract_tables: false`
- Use smaller chunk size for ingestion
- Parallelize: run multiple parse replicas

#### Poor Table Extraction

**Symptoms**: Tables not detected, garbled markdown

**Fixes**:
- Ensure PDF is text-based (not scanned)
- Try Docling as alternative
- Pre-process: rotate, deskew, enhance contrast

### 5. Guardrails

#### False Positives

**Symptoms**: Legitimate queries blocked

**Diagnosis**:
```bash
curl -X POST http://guardrails:8000/v1/guard \
  -d '{"text": "What is our revenue?", "tenant_id": "acme"}'
```

**Fixes**:
- Adjust PII entities list (remove `PERSON` if names are common)
- Add custom allowlist for domain terms
- Reduce sensitivity: `threshold: 0.7` (was 0.5)
- Add domain-specific rails

#### Guardrails Timeout

**Symptoms**: Guardrails takes >10s, query fails

**Fixes**:
```yaml
guardrails:
  timeout: 15  # Increase from 10
  # Or run async (non-blocking)
  async_mode: true
```

### 6. Keycloak (Auth)

#### Login Fails

**Symptoms**: "Invalid credentials", "Account locked"

**Diagnosis**:
```bash
kubectl logs keycloak-xxx | grep -i "login\|failed\|lock"
```

**Fixes**:
- Check brute force settings: `maxFailureWaitSeconds: 900`
- Verify password policy
- Check realm config: `loginWithEmailAllowed: true`

#### Token Validation Fails

**Symptoms**: 401 Unauthorized, "Token expired", "Invalid audience"

**Diagnosis**:
```bash
# Decode JWT
echo <token> | cut -d. -f2 | base64 -d | jq .
# Check: exp, iat, aud, iss
```

**Fixes**:
- Sync clocks: `ntpdate pool.ntp.org` on all nodes
- Verify `JWT_AUDIENCE` matches Keycloak client
- Check `JWT_ISSUER` matches Keycloak realm URL
- Ensure `JWT_PUBLIC_KEY` or JWKS URL accessible

#### SAML/OIDC Not Working

**Symptoms**: Redirect loops, "Invalid SAML response"

**Diagnosis**:
```bash
kubectl logs keycloak-xxx | grep -i "saml\|oidc"
# Check identity provider config
```

**Fixes**:
- Verify IdP metadata URL accessible
- Check certificate expiration
- Validate attribute mappings
- Check redirect URIs match exactly

### 7. Ingestion Pipeline

#### Documents Not Searchable

**Symptoms**: Ingestion succeeds but query returns no results

**Diagnosis**:
```bash
# Check Qdrant collection
curl http://qdrant:6333/collections/tenant_xxx/points/count

# Check ingestion logs
kubectl logs ingestion-xxx | grep -E "upsert|error|chunks"
```

**Fixes**:
- Verify tenant_id matches in ingestion and query
- Check embedding dimension matches collection (1024 for BGE-M3)
- Verify upsert completed: check Qdrant points count

#### Ingestion Stuck

**Symptoms**: Job stays "processing" forever

**Diagnosis**:
```bash
kubectl logs ingestion-xxx -f | tail -50
# Check for: Marker timeout, download failure, memory issue
```

**Fixes**:
- Add timeout to download: `timeout: 300`
- Split large files
- Add retry logic for transient failures
- Monitor ingestion queue depth

### 8. Network / Connectivity

#### Service-to-Service Timeout

**Symptoms**: "Connection refused", "Connection timed out"

**Diagnosis**:
```bash
# From rag-api pod
kubectl exec rag-api-xxx -- curl -v http://qdrant:6333/health
kubectl exec rag-api-xxx -- curl -v http://vllm-llm:8000/health

# Check NetworkPolicy
kubectl get networkpolicy -n rag-platform
kubectl describe networkpolicy rag-api-network-policy
```

**Fixes**:
- Verify NetworkPolicy allows traffic
- Check service names match (DNS)
- Verify ports match (8000 vs 80)
- Check mTLS if using Istio (PeerAuthentication)

#### DNS Resolution Fails

**Symptoms**: "Name or service not known"

**Fixes**:
- Use fully qualified names: `qdrant.rag-platform.svc.cluster.local`
- Check CoreDNS logs: `kubectl logs -n kube-system -l k8s-app=kube-dns`
- Verify service exists: `kubectl get svc -n rag-platform`

### 9. Monitoring / Observability

#### Missing Metrics

**Symptoms**: Grafana shows "No data", Prometheus targets down

**Diagnosis**:
```bash
# Check Prometheus targets
curl http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="rag-api")'

# Check service annotations
kubectl get pods -n rag-platform -l app=rag-api -o jsonpath='{.items[0].metadata.annotations}'
```

**Fixes**:
- Add Prometheus annotations to pods:
  ```yaml
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8000"
    prometheus.io/path: "/metrics"
  ```
- Verify ServiceMonitor exists (if using Prometheus Operator)

#### Langfuse Not Showing Traces

**Symptoms**: No traces in Langfuse UI

**Diagnosis**:
```bash
# Check Langfuse logs
kubectl logs langfuse-xxx | grep -i trace

# Check RAG API env vars
kubectl exec rag-api-xxx -- env | grep LANGFUSE
```

**Fixes**:
- Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`
- Verify `LANGFUSE_HOST` is correct (internal DNS)
- Check network connectivity to Langfuse

---

## Debugging Commands Cheat Sheet

```bash
# === Cluster Health ===
kubectl get nodes -o wide
kubectl get pods -n rag-platform -o wide
kubectl top nodes
kubectl top pods -n rag-platform

# === GPU ===
kubectl exec -n rag-platform vllm-llm-xxx -- nvidia-smi
kubectl exec -n rag-platform vllm-llm-xxx -- nvidia-smi dmon -s pucvmet

# === Logs ===
kubectl logs -n rag-platform -l app=rag-api --tail=100 -f
kubectl logs -n rag-platform -l app=vllm-llm --tail=100 -f
kubectl logs -n rag-platform -l app=qdrant --tail=100 -f

# === Service Health ===
curl -k https://rag.yourcompany.com/health
curl http://vllm-llm:8000/health
curl http://embed:8000/health
curl http://rerank:8000/health
curl http://qdrant:6333/health
curl http://guardrails:8000/health
curl http://keycloak:8080/health/ready

# === Qdrant ===
curl http://qdrant:6333/collections
curl http://qdrant:6333/collections/tenant_acme-corp
curl -X POST http://qdrant:6333/collections/tenant_acme-corp/points/search \
  -H "Content-Type: application/json" \
  -d '{"vector": {"name": "dense", "vector": [0.1]*1024}, "limit": 5}'

# === vLLM ===
curl http://vllm-llm:8000/v1/models
curl -X POST http://vllm-llm:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "Qwen2.5-14B-Instruct", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 10}'

# === Keycloak ===
curl http://keycloak:8080/realms/rag-platform/.well-known/openid-configuration
curl http://keycloak:8080/realms/rag-platform/protocol/openid-connect/certs

# === Network ===
kubectl exec -n rag-platform rag-api-xxx -- curl -v http://qdrant:6333/health
kubectl exec -n rag-platform rag-api-xxx -- nslookup qdrant
kubectl get networkpolicy -n rag-platform

# === Resources ===
kubectl describe pod -n rag-platform vllm-llm-xxx
kubectl top pod -n rag-platform --containers

# === Events ===
kubectl get events -n rag-platform --sort-by='.lastTimestamp'
kubectl get events -n rag-platform --field-selector type=Warning
```

---

## Escalation Matrix

| Severity | Response | Contacts |
|----------|----------|----------|
| **P0 - Critical** (Production down, data loss) | 15 min | On-call eng + Team lead + VP Eng |
| **P1 - High** (Major feature broken, security) | 1 hour | On-call eng + Team lead |
| **P2 - Medium** (Performance, minor bugs) | 4 hours | On-call eng |
| **P3 - Low** (Questions, enhancements) | 1 business day | Team |

### P0 Runbook
1. Acknowledge alert (15 min)
2. Check status page, post incident
3. Check cluster health (`kubectl get nodes`, `kubectl get pods -A`)
4. Check recent deployments (`kubectl rollout history`)
5. Check logs for error patterns
6. If unclear, rollback last deployment
7. Communicate every 30 min
8. Post-mortem within 48 hours

---

## Useful Queries

```promql
# High level
sum(rate(rag_queries_total[5m])) by (tenant)
histogram_quantile(0.99, rate(rag_query_latency_seconds_bucket[5m]))
rate(rag_queries_total{status="error"}[5m]) / rate(rag_queries_total[5m])

# vLLM
vllm_request_queue_depth
vllm_gpu_memory_used_bytes / vllm_gpu_memory_total_bytes
rate(vllm_token_total[1m])

# Qdrant
qdrant_collections_points_count
rate(qdrant_search_latency_seconds_sum[5m]) / rate(qdrant_search_latency_seconds_count[5m])

# Tenant
rag_tenant_storage_bytes / (rag_tenant_storage_quota_gb * 1024^3)
rate(rag_queries_total[1m]) * 60 / rag_tenant_qpm_limit

# GPU
nvidia_gpu_memory_used_bytes / nvidia_gpu_memory_total_bytes
nvidia_gpu_utilization
nvidia_gpu_temperature_celsius

# Cost
rate(rag_tenant_gpu_cost_total[1h]) * 3600 * 24
rate(rag_tenant_cost_usd_total[1h]) / rate(rag_queries_total[1h])
```