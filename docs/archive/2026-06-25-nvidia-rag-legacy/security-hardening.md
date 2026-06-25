# Enterprise Agentic RAG — Security Hardening Guide

## Security Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DEFENSE IN DEPTH LAYERS                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PERIMETER: WAF, DDoS Protection, Rate Limiting                     │   │
│  │  (Cloudflare / AWS Shield / Cloud Armor)                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  NETWORK: mTLS, Network Policies, Private Subnets, Zero Trust       │   │
│  │  (Istio / Linkerd / Cilium / Calico)                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  APPLICATION: Auth (OIDC/SAML), RBAC, API Keys, Input Validation    │   │
│  │  (Keycloak, Guardrails, FastAPI Security)                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  DATA: Encryption at Rest/Transit, Tokenization, PII Masking        │   │
│  │  (LUKS, TLS 1.3, Vault, Guardrails)                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  INFRASTRUCTURE: Immutable Containers, Signed Images, SBOM, Scanning │   │
│  │  (Cosign, Trivy, Syft, Kyverno)                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Network Security

### Network Policies (Kubernetes)

```yaml
# Default deny all ingress/egress
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: rag-platform
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
---
# Allow specific traffic
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: rag-api-ingress
  namespace: rag-platform
spec:
  podSelector:
    matchLabels:
      app: rag-api
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8000
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: qdrant
      ports:
        - protocol: TCP
          port: 6333
    # ... allow to vllm, embed, rerank, keycloak, postgres, redis
```

### Service Mesh (Istio)

```yaml
# Enable mTLS cluster-wide
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: rag-platform
spec:
  mtls:
    mode: STRICT
---
# Authorization policies
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: rag-api-authz
  namespace: rag-platform
spec:
  selector:
    matchLabels:
      app: rag-api
  rules:
    - from:
        - source:
            principals: ["cluster.local/ns/ingress-nginx/sa/ingress-nginx"]
      to:
        - operation:
            paths: ["/v1/*", "/health", "/metrics"]
```

### TLS Configuration

```nginx
# Traefik / NGINX TLS config
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;
ssl_session_timeout 1d;
ssl_session_cache shared:SSL:10m;
ssl_session_tickets off;

# HSTS
add_header Strict-Transport-Security "max-age=63072000" always;

# OCSP Stapling
ssl_stapling on;
ssl_stapling_verify on;
```

---

## 2. Authentication & Authorization

### Keycloak Hardening

```json
{
  "realm": "rag-platform",
  "passwordPolicy": "length(12) and upperCase(1) and lowerCase(1) and digits(1) and specialChars(1) and notRecentlyUsed(5) and notUsername and hashIterations(100000)",
  "bruteForceProtected": true,
  "maxFailureWaitSeconds": 900,
  "minimumQuickLoginWaitSeconds": 60,
  "quickLoginCheckMilliSeconds": 1000,
  "maxDeltaTimeSeconds": 30,
  "failureFactor": 3
}
```

### JWT Token Security

```python
# FastAPI JWT validation
JWT_CONFIG = {
    "algorithm": "RS256",
    "audience": "rag-platform",
    "issuer": "https://keycloak.rag.yourcompany.com/realms/rag-platform",
    "jwks_url": "https://keycloak.rag.yourcompany.com/realms/rag-platform/protocol/openid-connect/certs",
    "leeway": 30,
    "verify_exp": True,
    "verify_iat": True,
    "verify_nbf": True,
}
```

### RBAC Model

| Role | Permissions | Typical User |
|------|-------------|--------------|
| `admin` | All permissions, tenant management | Platform operator |
| `tenant-admin` | Query, ingest, manage users, view metrics, configure tenant | Customer admin |
| `analyst` | Query, ingest, view metrics | Power user |
| `user` | Query, view own data | End user |
| `api-client` | Query (service account) | Integration |
| `read-only` | Query only | Auditor |

### API Key Management

```python
# API key rotation
API_KEY_CONFIG = {
    "rotation_days": 90,
    "grace_period_days": 7,
    "max_keys_per_tenant": 5,
    "scopes": ["query", "ingest", "admin"],
    "rate_limit_override": True
}
```

---

## 3. Data Protection

### Encryption at Rest

```yaml
# PostgreSQL
postgresql:
  parameters:
    - name: "shared_preload_libraries"
      value: "pgcrypto"
    - name: "password_encryption"
      value: "scram-sha-256"

# Qdrant (PVC encryption)
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: qdrant-storage
spec:
  storageClassName: encrypted-ssd  # AWS EBS-GP3 encryption / GCP PD encryption
  resources:
    requests:
      storage: 200Gi

# MinIO (SSE-S3)
minio:
  env:
    - name: MINIO_KMS_SSE
      value: "sse-s3"
```

### Encryption in Transit

```yaml
# All service communication via mTLS
# Istio PeerAuthentication: STRICT mode
# Or Linkerd/Cilium for mTLS
```

### PII Protection (Guardrails)

```python
# Automatic PII detection and masking
GUARDRAILS_CONFIG = {
    "pii_entities": [
        "PERSON", "EMAIL", "PHONE", "CREDIT_CARD",
        "SSN", "PASSPORT", "DRIVER_LICENSE", "MEDICAL_RECORD",
        "BANK_ACCOUNT", "CRYPTO_WALLET", "IP_ADDRESS"
    ],
    "action": "mask",  # or "block", "anonymize"
    "mask_char": "█",
    "preserve_format": True
}
```

### Data Retention & Deletion

```yaml
# Automated retention policies
retention_policies:
  query_logs: 90 days
  ingestion_logs: 365 days
  model_traces: 30 days
  user_data: Per tenant config (default 365 days)
  backups: 90 days

# GDPR deletion
api_endpoint: "DELETE /v1/admin/tenants/{tenant_id}/users/{user_id}/data"
```

---

## 4. Container Security

### Image Hardening

```dockerfile
# Multi-stage build for minimal attack surface
FROM python:3.11-slim as builder
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim
# Non-root user
RUN groupadd -r app && useradd -r -g app app
# No shell, no package manager
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 && \
    rm -rf /var/lib/apt/lists/*
# Copy only needed files
COPY --from=builder /root/.local /home/app/.local
COPY --chown=app:app . /app
WORKDIR /app
USER app:app
# Read-only root filesystem
# (Set in K8s: readOnlyRootFilesystem: true)
```

### Image Signing & Verification

```bash
# Sign images with Cosign
cosign sign --key cosign.key enterprise-rag/rag-api:v1.0.0

# Verify in admission controller (Kyverno)
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-image-signatures
spec:
  validationFailureAction: Enforce
  rules:
    - name: check-cosign-signature
      match:
        any:
          - resources:
              kinds: ["Pod"]
      verifyImages:
        - image: "enterprise-rag/*"
          key: |-
            -----BEGIN PUBLIC KEY-----
            ...
            -----END PUBLIC KEY-----
```

### Vulnerability Scanning

```yaml
# CI/CD Pipeline
stages:
  - scan:
      script:
        - trivy image --severity HIGH,CRITICAL --exit-code 1 enterprise-rag/rag-api:${TAG}
        - syft packages enterprise-rag/rag-api:${TAG} -o spdx-json=sbom.spdx.json
        - grype sbom:sbom.spdx.json --fail-on HIGH
```

### Runtime Security (Falco)

```yaml
# Falco rules for runtime anomaly detection
- rule: Unexpected Network Connection
  desc: Detect unexpected outbound connections
  condition: >
    (evt.type=connect and fd.sip!=127.0.0.1 and
     not container.image.repository in (allowed_images))
  output: "Unexpected connection from %container.name to %fd.sip"
  priority: WARNING

- rule: Shell Spawned in Container
  desc: Detect interactive shell in production container
  condition: >
    (evt.type=execve and proc.name in (bash, sh, zsh, python))
  output: "Shell spawned in %container.name by %user.name"
  priority: ERROR
```

---

## 5. Application Security

### Input Validation

```python
# FastAPI automatic validation via Pydantic
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    tenant_id: Optional[str] = None
    retrieval_top_k: int = Field(default=20, ge=1, le=100)
    rerank_top_n: int = Field(default=5, ge=1, le=20)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
```

### Rate Limiting

```python
# Per-tenant, per-IP, per-user
RATE_LIMITS = {
    "query": {"requests": 60, "window": 60, "scope": "tenant"},      # 60 QPM
    "ingest": {"requests": 10, "window": 3600, "scope": "tenant"},   # 10/hr
    "auth": {"requests": 5, "window": 300, "scope": "ip"},           # 5/5min
    "admin": {"requests": 100, "window": 60, "scope": "user"},       # 100 QPM
}
```

### CORS Policy

```python
CORS_CONFIG = {
    "allow_origins": ["https://*.rag.yourcompany.com"],  # No wildcards in production
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Authorization", "Content-Type", "X-Tenant-ID", "X-API-Key"],
    "max_age": 3600,
}
```

### Security Headers

```python
# FastAPI middleware
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}
```

---

## 6. Monitoring & Incident Response

### Security Event Logging

```python
# Structured security logging
import structlog

security_logger = structlog.get_logger("security")

def log_security_event(event_type: str, **kwargs):
    security_logger.info(
        "security_event",
        event_type=event_type,
        timestamp=datetime.utcnow().isoformat(),
        **kwargs
    )

# Examples
log_security_event("login_success", user_id="xxx", tenant_id="yyy", ip="1.2.3.4")
log_security_event("login_failure", user_id="xxx", reason="invalid_password", ip="1.2.3.4")
log_security_event("api_key_created", tenant_id="yyy", created_by="admin@company.com")
log_security_event("data_access", tenant_id="yyy", user_id="xxx", resource="/v1/generate")
log_security_event("guardrails_violation", tenant_id="yyy", query="xxx", violation_type="pii")
```

### Alerting Rules

```yaml
# Prometheus alerts
groups:
  - name: security
    rules:
      - alert: HighLoginFailureRate
        expr: |
          rate(keycloak_login_failures_total[5m]) > 0.1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High login failure rate detected"

      - alert: APIKeyUsedFromNewIP
        expr: |
          changes(rag_api_key_usage{ip=~".+"}[1h]) > 0
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "API key used from new IP: {{ $labels.ip }}"

      - alert: GuardrailsViolationSpike
        expr: |
          rate(rag_guardrails_violations_total[5m]) > 10
        for: 3m
        labels:
          severity: warning
        annotations:
          summary: "Guardrails violations spike for tenant {{ $labels.tenant }}"

      - alert: UnauthorizedAccessAttempt
        expr: |
          rate(rag_unauthorized_access_total[5m]) > 0
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Unauthorized access attempt from {{ $labels.ip }}"
```

### Incident Response Playbook

```markdown
## Security Incident Response

### 1. Detection
- Alert triggers (Prometheus/Grafana/SIEM)
- User reports suspicious activity
- Automated anomaly detection

### 2. Triage (5 min)
- Confirm severity (Critical/High/Medium/Low)
- Identify affected tenants/systems
- Assign incident commander

### 3. Containment (15 min)
- Block malicious IPs at WAF
- Revoke compromised API keys
- Scale down affected services if needed

### 4. Eradication (30 min)
- Rotate all secrets for affected tenant
- Patch vulnerability
- Remove malicious artifacts

### 5. Recovery (1 hr)
- Restore from clean backup if needed
- Verify service health
- Re-enable access gradually

### 6. Post-Incident (24 hrs)
- Root cause analysis
- Update runbooks
- Implement preventive measures
```

---

## 7. Compliance

### SOC2 Type II

| Control | Implementation |
|---------|----------------|
| **CC6.1** (Access Control) | Keycloak RBAC, API keys, mTLS |
| **CC6.7** (Data Transmission) | TLS 1.3 everywhere, mTLS |
| **CC7.2** (Monitoring) | Prometheus/Grafana/Loki/Tempo, alerts |
| **CC8.1** (Change Management) | GitOps, signed images, CI/CD gates |
| **PI1.1** (Data Classification) | Tenant isolation, PII guardrails |

### GDPR

| Requirement | Implementation |
|-------------|----------------|
| **Art. 17** (Right to Erasure) | `DELETE /v1/admin/tenants/{id}/users/{user_id}/data` |
| **Art. 20** (Data Portability) | `GET /v1/admin/tenants/{id}/export` |
| **Art. 25** (Data Protection by Design) | Tenant isolation, encryption, PII masking |
| **Art. 30** (Records of Processing) | Audit logs, Langfuse traces |

### HIPAA (BAA-Ready)

| Safeguard | Implementation |
|-----------|----------------|
| **Access Control** | Keycloak + RBAC, MFA required |
| **Audit Controls** | Immutable logs, Langfuse traces |
| **Integrity** | TLS, signed images, encrypted PVCs |
| **Transmission Security** | mTLS everywhere |

---

## 8. Penetration Testing

### Annual Testing

```bash
# Scope
- External API (rag.yourcompany.com)
- Auth system (keycloak.rag.yourcompany.com)
- Ingestion pipeline
- Admin panel

# Tools
- OWASP ZAP (automated)
- Burp Suite (manual)
- Nuclei templates
- Custom scripts for RAG-specific attacks

# RAG-Specific Tests
- Prompt injection attempts
- Data exfiltration via queries
- Tenant isolation bypass
- Guardrails bypass
- Model hallucination exploitation
```

### Bug Bounty

```yaml
# Vulnerability rewards
critical: $5,000 - $10,000  # RCE, auth bypass, tenant isolation break
high: $2,000 - $5,000       # SQLi, significant data leak
medium: $500 - $2,000       # XSS, info disclosure
low: $100 - $500            # Minor issues
```

---

## 9. Security Checklist (Pre-Production)

- [ ] All images signed and verified
- [ ] Trivy/Gypsy scans pass (no HIGH/CRITICAL)
- [ ] Network policies applied and tested
- [ ] mTLS enabled for all service communication
- [ ] TLS 1.3 on all external endpoints
- [ ] Keycloak hardened (password policy, brute force, MFA)
- [ ] RBAC configured per tenant
- [ ] API keys rotate automatically
- [ ] Rate limiting on all endpoints
- [ ] CORS restricted to known domains
- [ ] Security headers on all responses
- [ ] Input validation on all API endpoints
- [ ] Guardrails enabled for all tenants
- [ ] PII detection configured
- [ ] Encryption at rest (PVC, MinIO, PostgreSQL)
- [ ] Encryption in transit (mTLS)
- [ ] Audit logging enabled (all auth, data access, admin actions)
- [ ] Alerting configured for security events
- [ ] Incident response plan documented
- [ ] Backup encryption verified
- [ ] Penetration test completed
- [ ] Compliance attestations collected

---

## 10. Ongoing Security Operations

### Weekly
- [ ] Review vulnerability scan results
- [ ] Check for image updates (base images, dependencies)
- [ ] Review failed login attempts
- [ ] Verify backup integrity

### Monthly
- [ ] Rotate API keys (automated)
- [ ] Review and update network policies
- [ ] Check certificate expiration
- [ ] Review user access (deprovision stale accounts)
- [ ] Update threat model

### Quarterly
- [ ] Penetration test
- [ ] Security training for team
- [ ] Update incident response playbook
- [ ] Review compliance status
- [ ] Third-party dependency audit

### Annually
- [ ] Full security assessment
- [ ] SOC2 audit
- [ ] BAA renewal (if applicable)
- [ ] Disaster recovery test
- [ ] Architecture review for new threats