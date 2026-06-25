# Enterprise Agentic RAG — Cost Optimization Guide

## Cost Breakdown

### Infrastructure Costs (Monthly, Spot Pricing)

| Component | Starter (Shared) | Professional (MIG) | Enterprise (Dedicated) |
|-----------|------------------|-------------------|----------------------|
| **GPU Compute** | $150 | $300 | $600-1000 |
| **Storage (SSD)** | $20 | $50 | $200 |
| **Network/Load Balancer** | $15 | $25 | $50 |
| **Monitoring** | $10 | $25 | $50 |
| **Backup** | $5 | $20 | $100 |
| **Total/Month** | **$200** | **$420** | **$1,000-1,400** |
| **Per Tenant (20 tenants)** | **$10** | **$21** | **$50-70** |

### SaaS Pricing & Margins

| Tier | Price/Mo | Infra Cost | Gross Margin |
|------|----------|------------|--------------|
| Starter | $499 | $10 | 98% |
| Professional | $1,999 | $21 | 99% |
| Enterprise | $4,999 | $50-70 | 98-99% |

---

## Optimization Strategies

### 1. GPU Optimization (60-80% of Cost)

#### Model Quantization
```yaml
# vLLM quantization configs
quantization_configs:
  fp8:
    vram_savings: "50%"
    quality_loss: "<1%"
    supported_models: ["Qwen2.5-14B", "Qwen2.5-32B"]
    command: "--quantization fp8"
  
  int4:
    vram_savings: "75%"
    quality_loss: "2-5%"
    supported_models: ["Qwen2.5-7B", "Qwen2.5-14B"]
    command: "--quantization awq"
  
  gptq:
    vram_savings: "70%"
    quality_loss: "1-3%"
    supported_models: ["All"]
    command: "--quantization gptq"
```

**Savings**: Run Qwen2.5-14B in FP8 (8GB) vs FP16 (16GB) → 50% VRAM reduction → can fit 2x models on same GPU.

#### Tensor Parallelism vs Pipeline Parallelism
```yaml
# Single GPU: tensor_parallel_size=1 (default)
# Multi-GPU: tensor_parallel_size=2 (split model across GPUs)
# For 32B on 2x A10G: each GPU gets 9GB
tensor_parallel_size: 2  # Requires multiple GPUs
```

#### CPU Offloading for Embed/Rerank
```yaml
# Move embed/rerank to CPU (saves 2-4 GB VRAM)
embed:
  device: cpu  # BGE-M3 is fast on CPU
rerank:
  device: cpu  # BGE-Reranker-v2 is fast on CPU
# Savings: 2-4 GB GPU memory
```

#### KV Cache Optimization
```yaml
# vLLM KV cache settings
vllm:
  gpu_memory_utilization: 0.85  # Leave 15% for OS
  block_size: 16  # Smaller blocks = less fragmentation
  enable_prefix_caching: true  # Cache common prefixes
  cpu_offload_gb: 4  # Offload cold KV cache to CPU
```

### 2. Spot Instance Strategy

| Workload | Instance Type | Savings | Risk |
|----------|---------------|---------|------|
| **API Serving** | On-Demand | 0% | None |
| **Batch Ingestion** | Spot | 60-90% | Interruption (use checkpointing) |
| **Model Training/Finetune** | Spot | 60-90% | Interruption (use checkpointing) |
| **Evaluation/Benchmark** | Spot | 60-90% | Interruption (idempotent) |

**Implementation**:
```yaml
# K8s node pools
nodePools:
  - name: on-demand-api
    instanceType: g5.xlarge (A10G)
    capacityType: ON_DEMAND
    minSize: 3
    maxSize: 20
  
  - name: spot-batch
    instanceType: g5.xlarge (A10G)
    capacityType: SPOT
    minSize: 0
    maxSize: 50
    taints:
      - key: "workload"
        value: "batch"
        effect: "NoSchedule"
```

---

### 3. Caching Strategy

#### Query Result Caching (Redis)

```python
# Cache frequent queries
CACHE_CONFIG = {
    "enabled": True,
    "ttl": 3600,  # 1 hour
    "max_size": 10000,
    "key_prefix": "rag:query:",
    # Cache key: hash(tenant_id + query + params)
}

# Cache hit rate target: >30% for typical workloads
# Typical queries: "What is our revenue?", "Summarize policy X"
```

#### Embedding Cache

```python
# Cache document embeddings for re-ingestion
EMBEDDING_CACHE = {
    "enabled": True,
    "storage": "redis",
    "ttl": 86400 * 7,  # 7 days
    # Key: hash(content + model_name)
}
```

#### vLLM Prefix Caching

```yaml
# vLLM automatic prefix caching
vllm:
  enable_prefix_caching: true
  # Automatically caches common prompt prefixes
  # Especially effective for system prompts, few-shot examples
```

---

### 4. Right-Sizing

#### Tenant-Aware Resource Allocation

```yaml
# Per-tenant resource limits
tenant_profiles:
  starter:
    gpu_share: 0.1  # 10% of GPU
    max_concurrent: 5
    queue_limit: 20
  
  professional:
    gpu_share: 0.5  # 50% of GPU (or dedicated MIG)
    max_concurrent: 20
    queue_limit: 100
  
  enterprise:
    gpu_share: 1.0  # Full GPU
    max_concurrent: 100
    queue_limit: 500
```

#### Horizontal Pod Autoscaler Tuning

```yaml
# HPA with custom metrics
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: rag-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: rag-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Pods
      pods:
        metric:
          name: rag_query_queue_depth
        target:
          type: AverageValue
          averageValue: "10"
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
        - type: Pods
          value: 3
          periodSeconds: 60
```

---

### 5. Storage Optimization

#### Qdrant Optimization

```yaml
# Qdrant config for cost efficiency
qdrant:
  # Quantization (reduces memory 4x)
  quantization:
    scalar:
      type: int8
      quantile: 0.99
      always_ram: true
  
  # On-disk payload (cheaper storage)
  on_disk_payload: true
  
  # HNSW tuning for memory/accuracy tradeoff
  hnsw_config:
    m: 16  # Lower = less memory, slightly less accuracy
    ef_construct: 100
    full_scan_threshold: 10000
  
  # WAL settings
  wal:
    enabled: true
    flush_interval: 1000
```

#### MinIO Lifecycle

```yaml
# Auto-tier to cheaper storage
lifecycle_rules:
  - name: "transition-to-ia"
    status: "Enabled"
    filter:
      prefix: "ingestion/"
    transitions:
      - days: 30
        storageClass: "STANDARD_IA"
      - days: 90
        storageClass: "GLACIER"
      - days: 365
        storageClass: "DEEP_ARCHIVE"
  
  - name: "delete-old-backups"
    status: "Enabled"
    filter:
      prefix: "backups/"
    expiration:
      days: 90
```

---

### 6. Monitoring Cost Allocation

#### Per-Tenant Cost Tracking

```python
# Prometheus metrics for cost attribution
metrics = {
    "rag_tenant_gpu_seconds_total": Counter(
        "gpu_seconds", "GPU seconds used", ["tenant", "model"]
    ),
    "rag_tenant_token_total": Counter(
        "tokens", "Tokens generated", ["tenant", "model", "type"]  # prompt/completion
    ),
    "rag_tenant_storage_bytes": Gauge(
        "storage_bytes", "Storage used", ["tenant"]
    ),
    "rag_tenant_api_calls_total": Counter(
        "api_calls", "API calls", ["tenant", "endpoint", "status"]
    ),
}

# Cost calculation (example)
def calculate_tenant_cost(tenant_id, period="1d"):
    gpu_hours = query(f'increase(rag_tenant_gpu_seconds_total{{tenant="{tenant_id}"}}[{period}])') / 3600
    prompt_tokens = query(f'sum(increase(rag_tenant_token_total{{tenant="{tenant_id}",type="prompt"}}[{period}]))')
    completion_tokens = query(f'sum(increase(rag_tenant_token_total{{tenant="{tenant_id}",type="completion"}}[{period}]))')
    storage_gb = query(f'rag_tenant_storage_bytes{{tenant="{tenant_id}"}}') / 1e9
    
    # Pricing (example)
    gpu_cost = gpu_hours * 0.45  # $0.45/hr spot A10G
    token_cost = (prompt_tokens * 0.0001 + completion_tokens * 0.0002) / 1000
    storage_cost = storage_gb * 0.10  # $0.10/GB/mo
    
    return {
        "gpu_cost": gpu_cost,
        "token_cost": token_cost,
        "storage_cost": storage_cost,
        "total": gpu_cost + token_cost + storage_cost
    }
```

#### Grafana Cost Dashboard

```json
{
  "dashboard": {
    "title": "Cost Tracking",
    "panels": [
      {"title": "Daily Cost by Tenant", "type": "graph", "targets": [{"expr": "rate(rag_tenant_cost_usd_total[1d])"}]},
      {"title": "Cost per Query", "type": "graph", "targets": [{"expr": "rate(rag_tenant_cost_usd_total[1h]) / rate(rag_queries_total[1h])"}]},
      {"title": "GPU Utilization vs Cost", "type": "graph", "targets": [{"expr": "nvidia_gpu_utilization * on(gpu) nvidia_gpu_estimated_cost_per_hour"}]},
    ]
  }
}
```

---

### 7. Cost Optimization Checklist

#### Immediate (Week 1)
- [ ] Enable FP8 quantization on all models
- [ ] Move embed/rerank to CPU
- [ ] Enable vLLM prefix caching
- [ ] Set up spot instance node pool for batch
- [ ] Configure Redis query caching
- [ ] Enable Qdrant scalar quantization
- [ ] Set up MinIO lifecycle policies
- [ ] Configure HPA with custom metrics

#### Short-term (Month 1)
- [ ] Implement per-tenant cost attribution
- [ ] Build Grafana cost dashboards
- [ ] Set up cost anomaly alerts
- [ ] Optimize HPA thresholds per tier
- [ ] Implement embedding cache
- [ ] Set up spot interruption handling

#### Ongoing (Monthly)
- [ ] Review cost per tenant vs tier pricing
- [ ] Identify top 10% cost tenants
- [ ] Negotiate reserved instances for baseline
- [ ] Benchmark new quantization methods
- [ ] Review and adjust tier limits
- [ ] Negotiate spot pricing with cloud provider

---

## Cost Modeling Example

### Scenario: 20 Tenants Mixed Tiers

| Tier | Count | GPU Allocation | Monthly Cost | Revenue | Margin |
|------|-------|----------------|--------------|---------|--------|
| Starter | 8 | Shared A10G (0.1 each) | $120 | $3,992 | 97% |
| Professional | 10 | MIG slices (1 each) | $1,500 | $19,990 | 93% |
| Enterprise | 2 | Dedicated A100 | $1,200 | $9,998 | 88% |
| **Total** | **20** | | **$2,820** | **$33,980** | **92%** |

### Break-even Analysis

| Fixed Costs/Month | Variable Cost/Tenant | Break-even Tenants (Starter) |
|-------------------|---------------------|-------------------------------|
| $2,000 (infra, monitoring, support) | $10 | 200 |
| $5,000 | $10 | 500 |
| $10,000 | $10 | 1,000 |

---

## Vendor Negotiation

### Cloud Provider Discounts

| Commitment | Discount | Best For |
|------------|----------|----------|
| 1-year Reserved | 30-40% | Baseline capacity |
| 3-year Reserved | 50-60% | Stable enterprise workloads |
| Savings Plans | 25-35% | Flexible usage |
| Spot Blocks | 60-90% | Batch/interruptible |
| Enterprise Agreement | Custom | >$100K/mo spend |

### Negotiation Levers
- Multi-cloud strategy (AWS + GCP + Azure)
- Committed spend growth (show trajectory)
- Reference customer / case study
- Early access / beta programs
- Technical partnership (NVIDIA, etc.)

---

## ROI Calculator

```python
def calculate_roi(tenants_by_tier, months=12):
    """Calculate ROI for RAG platform"""
    
    tier_pricing = {"starter": 499, "professional": 1999, "enterprise": 4999}
    tier_costs = {"starter": 10, "professional": 21, "enterprise": 60}
    
    monthly_revenue = sum(tier_pricing[t] * c for t, c in tenants_by_tier.items())
    monthly_cost = sum(tier_costs[t] * c for t, c in tenants_by_tier.items())
    
    annual_revenue = monthly_revenue * months
    annual_cost = monthly_cost * months + 50000  # + fixed costs
    
    roi = (annual_revenue - annual_cost) / annual_cost * 100
    
    return {
        "monthly_revenue": monthly_revenue,
        "monthly_cost": monthly_cost,
        "monthly_profit": monthly_revenue - monthly_cost,
        "annual_roi_percent": roi,
        "payback_months": 50000 / (monthly_revenue - monthly_cost) if monthly_revenue > monthly_cost else float('inf')
    }

# Example
tenants = {"starter": 50, "professional": 30, "enterprise": 10}
print(calculate_roi(tenants))
# {'monthly_revenue': 104920, 'monthly_cost': 1680, 'monthly_profit': 103240, 'annual_roi_percent': 1982.3, 'payback_months': 0.5}
```