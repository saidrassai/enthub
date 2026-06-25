# Enterprise Agentic RAG — Tenant Onboarding Guide

## Overview

This guide covers the complete tenant onboarding process from provisioning to production traffic.

---

## Onboarding Flow

```
Sales Lead → Technical Evaluation → Contract → Provisioning → Configuration → Go-Live → Monitoring
```

---

## Phase 1: Technical Evaluation (Week 1-2)

### Requirements Gathering

| Category | Questions |
|----------|-----------|
| **Data** | Volume (GB), document types (PDF, DOCX, HTML), languages, update frequency |
| **Queries** | Expected QPS, peak hours, latency requirements, complexity (simple/lookup vs complex/reasoning) |
| **Models** | Preferred LLM (Qwen/Llama/Gemma), need for VLM, custom fine-tunes |
| **Security** | Compliance (SOC2, HIPAA, GDPR), data residency, encryption requirements |
| **Integration** | SSO (SAML/OIDC), API access, existing data sources (S3, SharePoint, Confluence) |

### Proof of Concept

```bash
# Spin up dedicated PoC environment
./scripts/provision-tenant.sh poc-customer "PoC Customer" professional poc.rag.yourcompany.com

# Load sample data
./scripts/ingest-sample-data.sh poc-customer

# Run benchmark
python scripts/benchmark.py --tenant poc-customer --qps 50 --duration 300

# Run evaluation
python scripts/eval.py --tenant poc-customer --dataset eval/finance_qa.json
```

### Success Criteria
- [ ] P95 latency < 5s for typical queries
- [ ] Faithfulness score > 0.85 (RAGAS)
- [ ] Answer relevancy > 0.90
- [ ] Guardrails catching test violations
- [ ] SSO integration working

---

## Phase 2: Provisioning (Week 3)

### Automated Provisioning

```bash
# Production tenant
./scripts/provision-tenant.sh \
  acme-corp \
  "Acme Corporation" \
  enterprise \
  acme.rag.yourcompany.com
```

### What Gets Created

| Resource | Details |
|----------|---------|
| **K8s Namespace** | `tenant-acme-corp` with resource quotas |
| **Qdrant Collection** | `tenant_acme-corp` with hybrid search config |
| **MinIO Bucket** | `tenant-acme-corp` with versioning, encryption |
| **Keycloak Realm** | `acme-corp` with client, roles, SAML/OIDC config |
| **Monitoring** | Tenant-specific alerts, Grafana dashboard |
| **Platform Registry** | Tenant config in platform database |

### Tier Comparison

| Feature | Starter | Professional | Enterprise |
|---------|---------|--------------|------------|
| Max QPM | 60 | 300 | 1,000 |
| Storage | 10 GB | 100 GB | 1 TB |
| Agentic RAG | ❌ | ✅ | ✅ |
| VLM | ❌ | ✅ | ✅ |
| Guardrails | Basic | Full | Full + Custom |
| GPU | Shared | MIG slice | Dedicated |
| SLA | 99.5% | 99.9% | 99.95% |
| Backup | Daily | Hourly + Daily | Continuous |
| Support | Email | Slack + Email | Dedicated |

---

## Phase 3: Configuration (Week 3-4)

### 1. SSO Integration

#### SAML (Okta, Azure AD, Ping)
```yaml
# In Keycloak realm config
identityProviders:
  - alias: saml
    providerId: saml
    config:
      singleSignOnServiceUrl: "https://acme.okta.com/app/xxx/sso/saml"
      singleLogoutServiceUrl: "https://acme.okta.com/app/xxx/sso/saml"
      nameIDPolicyFormat: "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent"
      signatureAlgorithm: "RSA_SHA256"
      validateSignature: "true"
```

#### OIDC (Google, Microsoft, Generic)
```yaml
identityProviders:
  - alias: oidc
    providerId: oidc
    config:
      authorizationUrl: "https://accounts.google.com/o/oauth2/v2/auth"
      tokenUrl: "https://oauth2.googleapis.com/token"
      userInfoUrl: "https://openidconnect.googleapis.com/v1/userinfo"
      clientId: "xxx.apps.googleusercontent.com"
      clientSecret: "xxx"
      defaultScope: "openid profile email"
      useJwksUrl: "true"
      jwksUrl: "https://www.googleapis.com/oauth2/v3/certs"
      validateSignature: "true"
      issuer: "https://accounts.google.com"
```

### 2. Role Mapping

```yaml
# Map IdP groups to Keycloak roles
groupRoleMappings:
  - group: "acme-rag-admins"
    roles: ["tenant-admin", "query", "ingest", "manage-users", "view-metrics"]
  - group: "acme-rag-users"
    roles: ["query", "view-own-data"]
  - group: "acme-rag-analysts"
    roles: ["query", "ingest", "view-metrics"]
```

### 3. Data Source Configuration

#### S3/MinIO
```yaml
s3_buckets:
  - "acme-financial-reports"
  - "acme-legal-contracts"
  - "acme-hr-policies"
```

#### SharePoint
```yaml
sharepoint_sites:
  - "https://acme.sharepoint.com/sites/Finance"
  - "https://acme.sharepoint.com/sites/Legal"
```

#### Confluence
```yaml
confluence_spaces:
  - "FIN"
  - "LEG"
  - "HR"
```

### 4. Custom Guardrails

```yaml
# Add to tenant config
custom_guardrails:
  - "financial"      # Block investment advice
  - "pii-strict"     # Enhanced PII detection
  - "competitor"     # Block competitor names
  - "custom:acme-terms"  # Custom term list
```

Create custom rail:
```yaml
# src/guardrails/rails/acme-terms.rail
rail_name: "acme-terms"
validator: "guardrails.hub.CompetitorCheck"
params:
  competitors:
    - "CompetitorCorp"
    - "RivalInc"
  on_fail: "exception"
```

---

## Phase 4: Data Ingestion

### Initial Bulk Load

```bash
# Ingest from S3
python -m src.ingestion.pipeline \
  --tenant acme-corp \
  --source s3://acme-financial-reports/ \
  --content-type pdf \
  --chunk-strategy semantic \
  --extract-tables \
  --generate-summaries

# Ingest from SharePoint
python -m src.ingestion.pipeline \
  --tenant acme-corp \
  --source sharepoint://acme.sharepoint.com/sites/Finance \
  --content-type pdf
```

### Incremental Updates

```bash
# Scheduled daily (Airflow/Cron)
0 3 * * * python -m src.ingestion.pipeline \
  --tenant acme-corp \
  --source s3://acme-financial-reports/ \
  --incremental \
  --since-yesterday
```

### Monitoring Ingestion

Grafana Dashboard: `Tenant Ingestion`
- Documents processed/hour
- Chunk success rate
- Embedding latency
- Failed documents (with errors)

---

## Phase 5: Testing & Go-Live

### Pre-Launch Checklist

- [ ] All data ingested and searchable
- [ ] SSO login working for all user groups
- [ ] RBAC permissions verified
- [ ] Guardrails tested with adversarial inputs
- [ ] Latency benchmarks meet SLA
- [ ] Evaluation scores meet thresholds
- [ ] Monitoring alerts configured
- [ ] Backup verified (test restore)
- [ ] Runbook documented
- [ ] Support contacts exchanged

### Canary Launch

```bash
# Route 10% traffic to new tenant
kubectl patch ingress rag-ingress -n rag-platform \
  -p '{"spec":{"rules":[{"host":"acme.rag.yourcompany.com","http":{"paths":[{"path":"/v1","pathType":"Prefix","backend":{"service":{"name":"rag-api","port":{"number":80}}}}]}}]}}'

# Monitor for 24 hours
# Check: error rate, latency, guardrails triggers
```

### Full Launch

```bash
# Update DNS
# acme.rag.yourcompany.com -> ingress IP

# Enable 100% traffic
# Notify customer
```

---

## Phase 6: Ongoing Operations

### Monthly Reviews

| Metric | Target | Action if Missed |
|--------|--------|------------------|
| P95 Latency | < 5s | Scale vLLM, optimize retrieval |
| Availability | > 99.9% | Investigate root cause |
| Faithfulness | > 0.85 | Improve retrieval, adjust prompts |
| Storage Growth | < 20% MoM | Archive old data, increase quota |
| Cost per Query | < $0.01 | Optimize model, enable caching |

### Quarterly Business Review

- Usage trends
- Feature requests
- Model upgrade planning
- Cost optimization
- Security audit

---

## Support Escalation

| Severity | Response Time | Channel |
|----------|---------------|---------|
| **Critical** (Production down) | 15 min | Phone + Slack |
| **High** (Major feature broken) | 1 hour | Slack + Email |
| **Medium** (Minor issue) | 4 hours | Email |
| **Low** (Question/Enhancement) | 1 business day | Email |

**Escalation Path**: Support Engineer → Senior Engineer → Engineering Lead → VP Engineering

---

## FAQ

### Q: Can we use our own fine-tuned model?
**A:** Yes. Add to tenant's `allowed_models` and deploy as separate vLLM instance.

### Q: How do we handle GDPR deletion requests?
**A:** Use `DELETE /v1/admin/tenants/{tenant_id}/data?user_id=xxx` or full tenant deletion.

### Q: Can we export our data?
**A:** Yes. Full data export via `GET /v1/admin/tenants/{tenant_id}/export`.

### Q: What happens if we exceed quota?
**A:** Soft limit: warnings at 80%, 90%. Hard limit: 429 responses at 100%. Contact support for increase.

### Q: Can we run on our own cloud/on-prem?
**A:** Yes. Enterprise/On-Prem tier includes deployment manifests for your infrastructure.