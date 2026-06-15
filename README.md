# Enterprise Agentic RAG — Open Source Blueprint

**Production-ready, multi-tenant, fully open-source Agentic RAG platform**  
Built on NVIDIA RAG Blueprint architecture, stripped of proprietary NIMs/Nemotron, powered by best-in-class open models.

---

## 🎯 **Design Principles**

| Principle | Implementation |
|-----------|----------------|
| **Zero Vendor Lock-in** | Apache 2.0 / MIT licensed components only; swap any model/infra |
| **Enterprise-Grade** | Multi-tenancy, RBAC, audit logs, guardrails, SLA-ready observability |
| **Agentic by Default** | LangGraph plan-execute-reflect loop; not just retrieve-generate |
| **Cost-Optimized** | Runs on single A10G 24GB (14B model) or A100 40GB (32B + VLM) |
| **Cloud-Agnostic** | Docker Compose → K8s (EKS/GKE/AKS/On-prem) same artifacts |

---

## 🏗️ **Architecture Overview**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ENTERPRISE AGENTIC RAG PLATFORM                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  Tenant A   │  │  Tenant B   │  │  Tenant C   │  │  Tenant N   │       │
│  │ (Isolated)  │  │ (Isolated)  │  │ (Shared)    │  │  (Dedicated)│       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │                │                │                │               │
│         ▼                ▼                ▼                ▼               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    API GATEWAY (Traefik)                            │   │
│  │  • mTLS • Rate Limiting • Tenant Routing • Auth Proxy • SSL Term   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                      │
│         ┌──────────────────────────┼──────────────────────────┐           │
│         ▼                          ▼                          ▼           │
│  ┌─────────────┐           ┌─────────────┐           ┌─────────────┐     │
│  │ RAG Pod A   │           │ RAG Pod B   │           │ RAG Pod N   │     │
│  │ (Dedicated) │           │ (MIG Slice) │           │ (Shared)    │     │
│  ├─────────────┤           ├─────────────┤           ├─────────────┤     │
│  │ • LangGraph │           │ • LangGraph │           │ • LangGraph │     │
│  │ • vLLM      │           │ • vLLM      │           │ • vLLM      │     │
│  │ • Qdrant    │           │ • Qdrant    │           │ • Qdrant    │     │
│  │ • Guardrails│           │ • Guardrails│           │ • Guardrails│     │
│  └─────────────┘           └─────────────┘           └─────────────┘     │
│         │                          │                          │           │
│         └──────────────────────────┼──────────────────────────┘           │
│                                    ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    CONTROL PLANE                                     │   │
│  │  • Keycloak (Auth/RBAC)  • Tenant Operator  • Model Registry      │   │
│  │  • Langfuse (Observability)  • Backup/DR  • Config Manager        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🧩 **Component Stack (All Open Source)**

| Layer | Component | Model/Tech | License | Purpose |
|-------|-----------|------------|---------|---------|
| **LLM** | vLLM | Qwen2.5-32B-Instruct / Qwen2.5-14B-Instruct | Apache 2.0 | Reasoning, generation |
| **Embeddings** | txtai + BGE-M3 | BAAI/bge-m3 | MIT | Dense + sparse + ColBERT |
| **Reranker** | txtai + BGE-Reranker | BAAI/bge-reranker-v2-m3 | MIT | Cross-encoder reranking |
| **VLM** | vLLM | Qwen2-VL-7B-Instruct / Qwen2-VL-2B-Instruct | Apache 2.0 | Vision-language |
| **PDF Parse** | Marker | vikparuchuri/marker | Apache 2.0 | PDF → Markdown + tables |
| **Vector DB** | Qdrant | qdrant/qdrant | Apache 2.0 | Hybrid search, multi-tenancy |
| **Orchestration** | LangGraph | Custom agentic graph | MIT | Plan-Execute-Reflect |
| **Guardrails** | Guardrails AI | Llama Guard 3 / custom rails | Apache 2.0 | PII, topic, safety |
| **Auth/RBAC** | Keycloak | Keycloak/Keycloak | Apache 2.0 | OIDC, SAML, multi-tenant |
| **API Gateway** | Traefik | traefik/traefik | MIT | mTLS, routing, rate limit |
| **Observability** | Langfuse | langfuse/langfuse | MIT | LLM traces, eval, costs |
| **Metrics** | Prometheus + Grafana | prom/prometheus, grafana/grafana | Apache 2.0 | Infra + app metrics |
| **Logging** | Loki + Promtail | grafana/loki | AGPL-3.0 | Log aggregation |
| **Tracing** | Tempo | grafana/tempo | AGPL-3.0 | Distributed tracing |

---

## 🚀 **Quick Start (Development)**

```bash
# Prerequisites: Docker 24+, Docker Compose v2, 24GB+ GPU (A10G/3090/4090)
cd /home/ubuntu/projects/nvidia-agentic-rag

# 1. Configure environment
cp deploy/docker/.env.example deploy/docker/.env
# Edit .env with your HF_TOKEN (for gated models) and domain

# 2. Start stack
cd deploy/docker
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d

# 3. Verify
curl http://localhost/health
curl -X POST http://localhost/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"query": "What is this system?", "tenant_id": "demo"}'

# 4. Access UIs
# - RAG API: http://localhost/v1
# - Langfuse: http://localhost:3000 (admin/admin)
# - Grafana: http://localhost:3001 (admin/prom-operator)
# - Keycloak: http://localhost:8080 (admin/admin)
# - Qdrant: http://localhost:6333/dashboard
```

---

## 📁 **Project Structure**

```
nvidia-agentic-rag/
├── deploy/
│   ├── docker/
│   │   ├── docker-compose.yml          # Core services
│   │   ├── docker-compose.gpu.yml      # GPU overrides
│   │   ├── docker-compose.cpu.yml      # CPU-only (llama.cpp)
│   │   ├── .env.example                # Environment template
│   │   ├── traefik/                    # API Gateway config
│   │   └── nginx/                      # Alternative gateway
│   └── k8s/
│       ├── base/                       # Kustomize base
│       │   ├── namespace.yaml
│       │   ├── rag-deployment.yaml
│       │   ├── qdrant-statefulset.yaml
│       │   ├── vllm-deployment.yaml
│       │   ├── keycloak-deployment.yaml
│       │   ├── langfuse-deployment.yaml
│       │   ├── monitoring-stack.yaml
│       │   ├── ingress.yaml
│       │   ├── network-policies.yaml
│       │   └── kustomization.yaml
│       └── overlays/
│           ├── dev/
│           │   ├── kustomization.yaml
│           │   └── values.yaml
│           └── prod/
│               ├── kustomization.yaml
│               ├── values.yaml
│               └── hpa.yaml
├── src/
│   ├── rag-api/                        # LangGraph Agentic RAG
│   │   ├── agent/
│   │   │   ├── graph.py                # StateGraph definition
│   │   │   ├── nodes.py                # Plan/Retrieve/Rerank/Generate/Reflect
│   │   │   ├── state.py                # TypedDict state
│   │   │   └── tools.py                # Search, rerank, generate tools
│   │   ├── api/
│   │   │   ├── routes.py               # FastAPI routes
│   │   │   ├── schemas.py              # Pydantic models
│   │   │   └── dependencies.py         # Auth, tenant, rate limit deps
│   │   ├── core/
│   │   │   ├── config.py               # Settings management
│   │   │   ├── tenants.py              # Tenant context/resolution
│   │   │   └── security.py             # JWT, API key validation
│   │   ├── services/
│   │   │   ├── llm.py                  # vLLM client
│   │   │   ├── embed.py                # txtai embeddings client
│   │   │   ├── rerank.py               # txtai reranker client
│   │   │   ├── vector.py               # Qdrant client
│   │   │   ├── parse.py                # Marker PDF client
│   │   │   └── guardrails.py           # Guardrails AI client
│   │   ├── main.py                     # App entrypoint
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── pyproject.toml
│   ├── guardrails/
│   │   ├── rails/                      # Guardrails AI rail specs
│   │   │   ├── pii.rail
│   │   │   ├── topic.rail
│   │   │   ├── safety.rail
│   │   │   └── financial.rail
│   │   ├── server.py                   # Guardrails server
│   │   └── Dockerfile
│   ├── auth/
│   │   ├── keycloak-config/            # Realm, clients, roles export
│   │   │   ├── realm-export.json
│   │   │   ├── clients/
│   │   │   └── roles/
│   │   ├── operator/                   # Tenant provisioning operator
│   │   │   ├── crd.yaml
│   │   │   ├── controller.py
│   │   │   └── Dockerfile
│   │   └── middleware.py               # FastAPI auth middleware
│   ├── ingestion/
│   │   ├── pipeline.py                 # Ingestion pipeline (LangChain)
│   │   ├── connectors/                 # SharePoint, S3, Confluence, etc.
│   │   ├── chunking.py                 # Semantic chunking strategies
│   │   ├── transformer.py              # Marker + table extraction
│   │   └── Dockerfile
│   └── monitoring/
│       ├── langfuse-dashboards/        # Pre-built Langfuse dashboards
│       ├── grafana-dashboards/         # JSON dashboards
│       │   ├── rag-overview.json
│       │   ├── tenant-usage.json
│       │   ├── model-performance.json
│       │   └── cost-tracking.json
│       └── prometheus-rules/           # Alerting rules
│           ├── rag-alerts.yml
│           └── infra-alerts.yml
├── config/
│   ├── models/
│   │   ├── model-registry.yaml         # Available models per tier
│   │   ├── vllm-profiles.yaml          # vLLM configs (TP, quantization)
│   │   └── fallback-models.yaml        # Fallback chain
│   ├── tenant/
│   │   ├── tiers.yaml                  # Starter/Pro/Enterprise tiers
│   │   ├── default-quotas.yaml         # Rate limits, storage, models
│   │   └── tier-configs/               # Per-tier overrides
│   ├── grafana/
│   │   ├── datasources.yaml
│   │   └── dashboards.yaml
│   └── prometheus/
│       ├── prometheus.yml
│       └── alertmanager.yml
├── scripts/
│   ├── provision-tenant.sh             # One-command tenant creation
│   ├── backup.sh                       # Qdrant + MinIO + Postgres backup
│   ├── restore.sh                      # Disaster recovery
│   ├── update-models.sh                # Rolling model updates
│   ├── benchmark.py                    # Load testing
│   └── eval.py                         # RAGAS evaluation
├── docs/
│   ├── architecture.md
│   ├── deployment-guide.md
│   ├── tenant-onboarding.md
│   ├── model-selection.md
│   ├── security-hardening.md
│   ├── cost-optimization.md
│   └── troubleshooting.md
└── tests/
    ├── integration/
    ├── unit/
    └── e2e/
```

---

## 🔐 **Multi-Tenancy Model**

| Tier | Isolation | GPU | Vector DB | NIMs | Max QPM | Storage | SLA |
|------|-----------|-----|-----------|------|---------|---------|-----|
| **Starter** | Logical (Qdrant partition + RBAC) | Shared pool | Shared cluster | Shared pool | 60 | 10 GB | 99.5% |
| **Professional** | MIG slice (1g.10gb) | Dedicated MIG | Dedicated DB | Dedicated replicas | 300 | 100 GB | 99.9% |
| **Enterprise** | Dedicated GPU node(s) | Dedicated GPU(s) | Dedicated cluster | Dedicated replicas | 1000+ | 1 TB+ | 99.95% |
| **On-Prem** | Customer infrastructure | Customer GPU | Customer DB | Customer NIMs | Unlimited | Unlimited | Custom |

---

##  **Guardrails Coverage**

| Category | Implementation | Models |
|----------|----------------|--------|
| **PII Detection** | Guardrails AI `DetectPII` + custom regex | Llama Guard 3 / Presidio |
| **Topic Control** | Guardrails AI `ValidTopics` | Custom taxonomy per tenant |
| **Content Safety** | Guardrails AI `LlamaGuard` | Llama Guard 3 8B |
| **Financial Advice** | Custom rail + regex | Jurisdiction-specific |
| **Hallucination** | Self-consistency check + citation verification | LLM-as-judge |
| **Prompt Injection** | Guardrails AI `DetectJailbreak` | Prompt injection classifier |

---

##  **Observability Stack**

| Signal | Tool | Retention | Purpose |
|--------|------|-----------|---------|
| **LLM Traces** | Langfuse | 90 days | Prompt/response, latency, tokens, costs |
| **Metrics** | Prometheus + Grafana | 1 year | QPS, latency, error rate, GPU util, queue depth |
| **Logs** | Loki + Promtail | 30 days | Debug, audit, ingestion pipeline |
| **Traces** | Tempo | 14 days | Distributed request tracing |
| **Alerts** | Alertmanager | — | PagerDuty, Slack, Email, OpsGenie |

---

##  **Cost Model (Cloud Spot Pricing)**

| Deployment | GPU | Monthly (24/7 spot) | Per-Tenant (Pro tier, 20 tenants) |
|------------|-----|---------------------|-----------------------------------|
| **Single A100 40GB** | 1× A100 40GB | ~$612 | $30 GPU + $10 infra = **$40/tenant** |
| **A100 80GB (MIG 7×)** | 1× A100 80GB | ~$1,008 | $144 GPU/7 = $20 + $10 = **$30/tenant** |
| **4× A10G 24GB** | 4× A10G | ~$1,296 | $65 GPU + $15 = **$80/tenant** |
| **On-Prem (Customer)** | Customer HW | $0 cloud | **$0 infrastructure** |

> **Your SaaS Margin**: Charge $499-4,999/mo per tier → 90%+ gross margin on GPU.

---

##  **Production Checklist**

- [ ] **TLS Everywhere**: mTLS between all services, Let's Encrypt for ingress
- [ ] **Secrets Management**: Vault/SealedSecrets for API keys, DB passwords
- [ ] **Network Policies**: K8s NetworkPolicy per tenant namespace
- [ ] **Resource Quotas**: CPU/RAM/GPU/Storage per tenant
- [ ] **Backup/DR**: Velero + Qdrant snapshots + MinIO replication (RPO < 1h, RTO < 4h)
- [ ] **Chaos Engineering**: LitmusChaos GPU failure, network partition tests
- [ ] **SOC2 Ready**: Audit logs, access reviews, encryption at rest/flight
- [ ] **Capacity Planning**: HPA/VPA for pods, Cluster Autoscaler for GPU nodes
- [ ] **Model Governance**: Model registry, versioning, rollback, A/B testing
- [ ] **Cost Attribution**: Per-tenant GPU hours, token counts, storage

---

##  **Documentation**

| Doc | Description |
|-----|-------------|
| [Architecture](docs/architecture.md) | Detailed component diagram, data flows |
| [Deployment Guide](docs/deployment-guide.md) | Docker → K8s, GPU setup, scaling |
| [Tenant Onboarding](docs/tenant-onboarding.md) | Provisioning, configuration, migration |
| [Model Selection](docs/model-selection.md) | Benchmarks, VRAM, latency, quality tradeoffs |
| [Security Hardening](docs/security-hardening.md) | CIS benchmarks, compliance, pen test |
| [Cost Optimization](docs/cost-optimization.md) | Spot, MIG, quantization, caching strategies |
| [Troubleshooting](docs/troubleshooting.md) | Common issues, debug procedures |

---

## 🤝 **Contributing**

This blueprint is **Apache 2.0 licensed**. Fork, modify, deploy, sell — no restrictions.

```bash
# Your fork
git clone https://github.com/YOUR-ORG/nvidia-agentic-rag
# Customize models, tiers, branding
# Deploy to your customers
```

---

##  **Support**

| Channel | Purpose |
|---------|---------|
| **GitHub Issues** | Bugs, feature requests |
| **Discussions** | Architecture questions, best practices |
| **Enterprise Support** | Your SaaS offering (SLAs, dedicated engineers) |

---

**Built from NVIDIA RAG Blueprint architecture, liberated for the open source community.**
