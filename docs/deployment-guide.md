# Enterprise Agentic RAG — Deployment Guide

## Prerequisites

### Infrastructure
- **Kubernetes**: 1.28+ (EKS, GKE, AKS, or on-prem)
- **GPU Nodes**: NVIDIA A10G (24GB) minimum, A100 40GB/80GB recommended
- **Storage**: Fast SSD (NVMe) for Qdrant, PostgreSQL, MinIO
- **Network**: Load balancer, DNS, TLS certificates
- **GPU Operator**: NVIDIA GPU Operator installed on cluster

### Software
- `kubectl` configured for target cluster
- `helm` 3.12+
- `kustomize` 5.0+
- `docker` 24+ (for building images)
- `minio/mc` CLI (for object storage)

---

## Quick Start (Development)

```bash
# 1. Clone and configure
git clone https://github.com/your-org/nvidia-agentic-rag
cd nvidia-agentic-rag

# 2. Configure environment
cp deploy/docker/.env.example deploy/docker/.env
# Edit .env with your values (HF_TOKEN, DOMAIN, passwords)

# 3. Start development stack
cd deploy/docker
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d

# 4. Verify
curl http://localhost/health
curl -X POST http://localhost/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello world", "tenant_id": "demo"}'

# 5. Access UIs
# - API: http://localhost/v1
# - Langfuse: http://localhost:3000 (admin/admin)
# - Grafana: http://localhost:3001 (admin/prom-operator)
# - Keycloak: http://localhost:8080 (admin/admin)
# - Qdrant: http://localhost:6333/dashboard
```

---

## Production Deployment (Kubernetes)

### 1. Prepare Cluster

```bash
# Install NVIDIA GPU Operator
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm install gpu-operator nvidia/gpu-operator -n gpu-operator --create-namespace

# Install Prometheus Operator (for monitoring)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack -n monitoring --create-namespace

# Install Cert Manager (for TLS)
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager -n cert-manager --create-namespace --version v1.13.0 --set installCRDs=true

# Install NGINX Ingress
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace
```

### 2. Configure Secrets

```bash
# Create namespace
kubectl apply -f deploy/k8s/base/namespace.yaml

# Create secrets (update values!)
kubectl create secret generic rag-secrets -n rag-platform \
  --from-literal=POSTGRES_PASSWORD="$(openssl rand -base64 32)" \
  --from-literal=KEYCLOAK_ADMIN_PASSWORD="$(openssl rand -base64 32)" \
  --from-literal=KEYCLOAK_DB_PASSWORD="$(openssl rand -base64 32)" \
  --from-literal=KEYCLOAK_CLIENT_SECRET="$(openssl rand -base64 32)" \
  --from-literal=MINIO_ROOT_PASSWORD="$(openssl rand -base64 32)" \
  --from-literal=HF_TOKEN="your-hf-token" \
  --from-literal=JWT_SECRET_KEY="$(openssl rand -base64 32)" \
  --from-literal=LANGFUSE_NEXTAUTH_SECRET="$(openssl rand -base64 32)" \
  --from-literal=LANGFUSE_SECRET_KEY="$(openssl rand -base64 32)" \
  --from-literal=LANGFUSE_SALT="$(openssl rand -base64 32)" \
  --from-literal=LANGFUSE_DATABASE_URL="postgresql://rag:PASSWORD@postgres:5432/langfuse" \
  --from-literal=GRAFANA_PASSWORD="$(openssl rand -base64 32)" \
  --from-literal=ADMIN_API_KEYS="$(openssl rand -base64 32)"
```

### 3. Deploy with Kustomize

```bash
# Development
kubectl apply -k deploy/k8s/overlays/dev

# Production
kubectl apply -k deploy/k8s/overlays/prod
```

### 4. Verify Deployment

```bash
# Check all pods running
kubectl get pods -n rag-platform

# Check services
kubectl get svc -n rag-platform

# Check ingress
kubectl get ingress -n rag-platform

# Test API
curl -k https://rag.yourcompany.com/health
```

---

## GPU Configuration

### Single GPU (A10G 24GB / A100 40GB)
```yaml
# Uses Qwen2.5-14B (8GB VRAM) + embed/rerank on same GPU
resources:
  requests:
    nvidia.com/gpu: "1"
  limits:
    nvidia.com/gpu: "1"
```

### Multi-GPU (A100 80GB with MIG)
```yaml
# 7 MIG slices (1g.10gb each)
# Deploy 7 vLLM instances, each on dedicated MIG slice
resources:
  requests:
    nvidia.com/gpu: "1"
    nvidia.com/mig-1g.10gb: "1"
  limits:
    nvidia.com/gpu: "1"
    nvidia.com/mig-1g.10gb: "1"
```

### Model Selection by GPU

| GPU VRAM | Recommended LLM | Config |
|----------|-----------------|--------|
| 24GB (A10G) | Qwen2.5-14B | `tensor_parallel_size: 1` |
| 40GB (A100) | Qwen2.5-14B + VLM | `tensor_parallel_size: 1` |
| 40GB (A100) | Qwen2.5-32B | `tensor_parallel_size: 1` |
| 80GB (A100) | Qwen2.5-32B + VLM | `tensor_parallel_size: 1` |
| 80GB MIG (×7) | Qwen2.5-14B each | 1 model per MIG slice |

---

## Tenant Onboarding

### Automated Provisioning
```bash
./scripts/provision-tenant.sh acme-corp "Acme Corporation" professional acme.rag.yourcompany.com
```

This creates:
- Kubernetes namespace `tenant-acme-corp`
- Qdrant collection `tenant_acme-corp`
- MinIO bucket `tenant-acme-corp`
- Keycloak realm/client for `acme-corp`
- Monitoring alerts for tenant
- Platform tenant registration

### Manual Configuration

Tenant config stored in ConfigMap `tenant-config` in tenant namespace:

```yaml
tenant_id: "acme-corp"
name: "Acme Corporation"
tier: "professional"
max_qpm: 300
max_storage_gb: 100
enable_agentic: true
enable_guardrails: true
enable_vlm: true
allowed_models:
  - "Qwen/Qwen2.5-14B-Instruct"
  - "Qwen/Qwen2.5-7B-Instruct"
```

---

## Monitoring & Alerting

### Access Dashboards
- **Grafana**: https://grafana.rag.yourcompany.com
  - RAG Overview: `rag-overview`
  - Tenant Usage: `tenant-usage`
  - Model Performance: `model-performance`
  - Cost Tracking: `cost-tracking`

- **Langfuse**: https://langfuse.rag.yourcompany.com
  - LLM traces, costs, prompt management

- **Prometheus**: https://prometheus.rag.yourcompany.com
  - Raw metrics, alerting rules

### Key Alerts
| Alert | Severity | Action |
|-------|----------|--------|
| `RAGQueryHighLatency` | Warning | Check vLLM queue, scale pods |
| `RAGQueryHighErrorRate` | Warning | Check logs, service health |
| `VLLMHighGPUMemory` | Warning | Reduce batch size, scale GPU |
| `QdrantDiskSpaceLow` | Warning | Expand PVC, cleanup old data |
| `TenantStorageQuotaExceeded` | Warning | Notify tenant, increase quota |

---

## Backup & Disaster Recovery

### Scheduled Backups
```bash
# Daily full backup (cronjob)
0 2 * * * /scripts/backup.sh all s3://rag-backups/$(date +%Y%m%d)

# Hourly incremental (tenant data)
0 * * * * /scripts/backup.sh acme-corp s3://rag-backups/incremental/acme-corp
```

### Restore Procedure
```bash
# Full restore
./scripts/restore.sh s3://rag-backups/20241215-020000

# Tenant-only restore
./scripts/restore.sh s3://rag-backups/20241215-020000 acme-corp
```

**RPO**: 1 hour (incremental) / 24 hours (full)
**RTO**: < 4 hours (tested)

---

## Security Hardening

### Network Policies
- All inter-service communication restricted by `NetworkPolicy`
- Ingress only via NGINX with rate limiting
- Egress blocked by default, explicit allow for dependencies

### Encryption
- **In Transit**: mTLS via Istio/Linkerd or NGINX
- **At Rest**: PVC encryption (AWS EBS/GCP PD/Azure Disk)
- **Secrets**: SealedSecrets or Vault

### Compliance
- **SOC2**: Audit logging, access reviews, encryption
- **GDPR**: Data deletion, retention policies, DPA
- **HIPAA**: PHI guardrails, BAA-ready infrastructure

---

## Scaling

### Horizontal Pod Autoscaler (HPA)
```yaml
# rag-api HPA (in prod overlay)
minReplicas: 3
maxReplicas: 20
metrics:
  - CPU: 70%
  - Memory: 80%
  - Custom: rag_query_queue_depth > 10
```

### Cluster Autoscaler
```yaml
# GPU node group scaling
- GPU nodes: 1-10 (on-demand)
- GPU nodes: 0-20 (spot, for batch ingestion)
```

### Qdrant Scaling
- **Vertical**: Increase PVC size, memory limits
- **Horizontal**: Qdrant cluster mode (3+ nodes)
- **Sharding**: By tenant (tenant per collection)

---

## Upgrades

### Rolling Model Update
```bash
./scripts/update-models.sh Qwen/Qwen2.5-14B-Instruct v1.1
```

### Platform Upgrade
```bash
# 1. Backup
./scripts/backup.sh all s3://rag-backups/pre-upgrade-$(date +%Y%m%d)

# 2. Apply new manifests
kubectl apply -k deploy/k8s/overlays/prod

# 3. Verify
kubectl rollout status deployment/rag-api -n rag-platform
```

---

## Troubleshooting

### Common Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| High latency | vLLM queue full | Scale vLLM replicas, check GPU memory |
| OOM errors | Model too large for GPU | Use smaller model, enable quantization |
| Qdrant slow | Disk I/O bottleneck | Use faster SSD, increase cache |
| Auth failures | Keycloak token expired | Check clock sync, token lifespans |
| Ingestion fails | PDF parsing error | Check Marker logs, file format |

### Debug Commands
```bash
# Check pod logs
kubectl logs -n rag-platform -l app=rag-api --tail=100 -f

# Check vLLM metrics
curl http://vllm-llm:8000/metrics

# Check Qdrant health
curl http://qdrant:6333/health

# Check GPU usage
kubectl exec -n rag-platform vllm-llm-xxx -- nvidia-smi

# Network connectivity
kubectl exec -n rag-platform rag-api-xxx -- curl -v http://qdrant:6333/health
```

---

## Cost Optimization

### Spot Instances
- Use spot for batch ingestion workers (60-90% savings)
- Keep primary API on on-demand

### Model Quantization
- Qwen2.5-14B: FP8 (8GB) vs FP16 (16GB) - 50% VRAM savings
- Enable vLLM FP8 quantization

### Caching
- Enable KV cache in vLLM
- Cache frequent queries in Redis
- Cache embeddings for repeated documents

### Right-sizing
| Tier | GPU | Monthly (Spot) | Monthly (On-Demand) |
|------|-----|----------------|---------------------|
| Starter | Shared A10G | $150 | $400 |
| Pro | MIG 1g.10gb | $300 | $800 |
| Enterprise | Dedicated A100 40GB | $600 | $1,800 |

---

## Support

- **Documentation**: This guide + `/docs` folder
- **Issues**: GitHub Issues
- **Enterprise Support**: Your SaaS agreement (SLAs, dedicated engineers)