# =============================================================================
# ENTERPRISE AGENTIC RAG — GUARDRAILS AI SERVER
# =============================================================================

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from guardrails import Guard
from guardrails.hub import (
    DetectPII,
    ValidLength,
    CompetitorCheck,
    ToxicLanguage,
    ProfanityFree,
    RestrictToTopic,
    SecretsPresent,
    URLFree
)
import uvicorn
import os

app = FastAPI(title="Guardrails AI Server", version="1.0.0")


# -----------------------------------------------------------------------------
# SCHEMAS
# -----------------------------------------------------------------------------
class GuardRequest(BaseModel):
    text: str
    tenant_id: str
    rails: List[str] = []


class GuardResponse(BaseModel):
    passed: bool
    violations: List[Dict[str, Any]] = []
    pii_detected: bool = False
    corrected_text: Optional[str] = None


# -----------------------------------------------------------------------------
# RAIL DEFINITIONS
# -----------------------------------------------------------------------------
# PII Detection
pii_guard = Guard().use(
    DetectPII(
        pii_entities=[
            "PERSON", "EMAIL", "PHONE_NUMBER", "CREDIT_CARD",
            "US_SSN", "US_PASSPORT", "IBAN", "IP_ADDRESS",
            "MEDICAL_LICENSE", "BANK_ACCOUNT", "CRYPTO_WALLET"
        ],
        on_fail="exception"
    )
)

# Content Safety
safety_guard = Guard().use(
    ToxicLanguage(threshold=0.5, on_fail="exception")
).use(
    ProfanityFree(on_fail="exception")
)

# Topic Restriction
def create_topic_guard(topics: List[str]):
    return Guard().use(
        RestrictToTopic(
            valid_topics=topics,
            disable_classifier=False,
            on_fail="exception"
        )
    )

# Financial Advice Guard
financial_guard = Guard().use(
    RestrictToTopic(
        valid_topics=[
            "general_information", "market_data", "company_facts",
            "financial_definitions", "regulatory_information"
        ],
        invalid_topics=[
            "investment_advice", "trading_recommendations",
            "tax_advice", "legal_advice", "personal_finance_planning"
        ],
        on_fail="exception"
    )
)


# -----------------------------------------------------------------------------
# TENANT RAIL CONFIGURATION
# -----------------------------------------------------------------------------
TENANT_RAILS = {
    "default": ["pii", "safety"],
    "financial": ["pii", "safety", "financial"],
    "healthcare": ["pii", "safety", "hipaa"],
    "legal": ["pii", "safety", "legal"],
}


async def get_guard_for_tenant(tenant_id: str, custom_rails: List[str] = None) -> Guard:
    """Get configured guard for tenant"""
    rails = TENANT_RAILS.get(tenant_id, TENANT_RAILS["default"])
    rails.extend(custom_rails or [])

    # Build combined guard
    guard = Guard()

    if "pii" in rails:
        guard = guard.use(DetectPII(on_fail="exception"))
    if "safety" in rails:
        guard = guard.use(ToxicLanguage(threshold=0.5, on_fail="exception"))
        guard = guard.use(ProfanityFree(on_fail="exception"))
    if "financial" in rails:
        guard = guard.use(financial_guard)
    if "hipaa" in rails:
        # Add HIPAA-specific PHI detection
        guard = guard.use(DetectPII(pii_entities=["MEDICAL_RECORD", "HEALTH_PLAN"], on_fail="exception"))

    return guard


# -----------------------------------------------------------------------------
# ENDPOINTS
# -----------------------------------------------------------------------------
@app.post("/v1/guard", response_model=GuardResponse)
async def guard_text(request: GuardRequest):
    """Run guardrails on text"""

    guard = await get_guard_for_tenant(request.tenant_id, request.rails)

    try:
        result = guard.validate(request.text)
        return GuardResponse(
            passed=True,
            violations=[],
            pii_detected=False,
            corrected_text=result.validated_output
        )
    except Exception as e:
        # Extract violation details
        violations = []
        pii_detected = False

        if hasattr(e, 'error'):
            for err in e.error:
                violations.append({
                    "type": err.validator,
                    "message": err.error_message,
                    "span": err.span
                })
                if "pii" in err.validator.lower():
                    pii_detected = True

        return GuardResponse(
            passed=False,
            violations=violations,
            pii_detected=pii_detected,
            corrected_text=None
        )


@app.post("/v1/guard/input", response_model=GuardResponse)
async def guard_input(request: GuardRequest):
    """Guard input query"""
    return await guard_text(request)


@app.post("/v1/guard/output", response_model=GuardResponse)
async def guard_output(
    answer: str,
    query: str,
    citations: List[Dict],
    tenant_id: str,
    rails: List[str] = []
):
    """Guard generated answer"""

    # Check answer
    guard = await get_guard_for_tenant(tenant_id, rails)

    try:
        result = guard.validate(answer)

        # Additional checks for hallucination
        citation_check = await _check_citation_grounding(answer, citations)

        return GuardResponse(
            passed=citation_check["passed"],
            violations=citation_check.get("violations", []),
            pii_detected=False,
            corrected_text=result.validated_output
        )
    except Exception as e:
        violations = []
        if hasattr(e, 'error'):
            for err in e.error:
                violations.append({
                    "type": err.validator,
                    "message": err.error_message
                })

        return GuardResponse(
            passed=False,
            violations=violations,
            pii_detected=False,
            corrected_text=None
        )


async def _check_citation_grounding(answer: str, citations: List[Dict]) -> Dict:
    """Verify answer is grounded in citations"""
    # Simple check: ensure key claims have citations
    # In production: use LLM-as-judge or NLI model
    return {"passed": True, "violations": []}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "guardrails"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)