# =============================================================================
# ENTERPRISE AGENTIC RAG — LANGGRAPH NODES
# =============================================================================
# Plan → Retrieve → Rerank → Generate → Reflect (loop)
# =============================================================================

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from .state import (
    RAGState, Document, Citation, TenantConfig, RetrievalStrategy,
    GenerationParams
)
from ..services import (
    LLMService, EmbeddingService, RerankService, VectorService,
    GuardrailsService, ParseService
)
from ..core.config import Settings
from ..core.tenants import TenantManager


class AgentNodes:
    """LangGraph node implementations for Agentic RAG"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm = LLMService(settings)
        self.embed = EmbeddingService(settings)
        self.rerank = RerankService(settings)
        self.vector = VectorService(settings)
        self.guardrails = GuardrailsService(settings)
        self.tenant_mgr = TenantManager(settings)
        self.parse = ParseService(settings)

    # -------------------------------------------------------------------------
    # PLAN NODE — Decompose complex query into sub-queries
    # -------------------------------------------------------------------------
    async def plan(self, state: RAGState, config: RunnableConfig) -> RAGState:
        """Analyze query and create execution plan"""

        tenant = await self.tenant_mgr.get_tenant(state["tenant_id"])

        if not state.get("enable_agentic", True) or not tenant.enable_agentic:
            return {
                "plan": [state["query"]],
                "sub_queries": [state["query"]],
                "current_sub_query": state["query"],
            }

        # Check if query is complex enough for decomposition
        complexity = await self._assess_complexity(state["query"])
        if complexity < 0.6:
            return {
                "plan": [state["query"]],
                "sub_queries": [state["query"]],
                "current_sub_query": state["query"],
            }

        # Decompose using LLM
        plan_prompt = f"""Analyze this query and decompose into 2-4 sub-queries for parallel retrieval.
Each sub-query should be specific and answerable independently.

Query: {state["query"]}

Return JSON array of sub-queries only. Example:
["What are the Q3 revenue figures?", "What were the YoY growth drivers?", "What guidance was given for Q4?"]"""

        response = await self.llm.chat(
            messages=[
                SystemMessage(content="You are a query decomposition expert. Return only valid JSON array."),
                HumanMessage(content=plan_prompt)
            ],
            temperature=0.1,
            max_tokens=500
        )

        try:
            sub_queries = json.loads(response.content)
            if not isinstance(sub_queries, list):
                sub_queries = [state["query"]]
        except json.JSONDecodeError:
            sub_queries = [state["query"]]

        return {
            "plan": sub_queries,
            "sub_queries": sub_queries,
            "current_sub_query": sub_queries[0] if sub_queries else state["query"],
            "iterations": 0,
        }

    # -------------------------------------------------------------------------
    # RETRIEVE NODE — Hybrid search across tenant collections
    # -------------------------------------------------------------------------
    async def retrieve(self, state: RAGState, config: RunnableConfig) -> RAGState:
        """Execute retrieval for current sub-query"""

        sub_query = state["current_sub_query"] or state["sub_queries"][0]
        tenant = await self.tenant_mgr.get_tenant(state["tenant_id"])

        # Build search filters for tenant isolation
        filters = {
            "tenant_id": state["tenant_id"],
            **state.get("metadata_filters", {})
        }

        # Execute retrieval based on strategy
        if state["retrieval_strategy"] == RetrievalStrategy.HYBRID:
            docs = await self._hybrid_search(sub_query, filters, state["retrieval_top_k"], tenant)
        elif state["retrieval_strategy"] == RetrievalStrategy.DENSE:
            docs = await self._dense_search(sub_query, filters, state["retrieval_top_k"], tenant)
        elif state["retrieval_strategy"] == RetrievalStrategy.SPARSE:
            docs = await self._sparse_search(sub_query, filters, state["retrieval_top_k"], tenant)
        elif state["retrieval_strategy"] == RetrievalStrategy.COLBERT:
            docs = await self._colbert_search(sub_query, filters, state["retrieval_top_k"], tenant)
        else:
            docs = await self._hybrid_search(sub_query, filters, state["retrieval_top_k"], tenant)

        return {"retrieved_docs": docs}

    # -------------------------------------------------------------------------
    # RERANK NODE — Cross-encoder reranking
    # -------------------------------------------------------------------------
    async def rerank(self, state: RAGState, config: RunnableConfig) -> RAGState:
        """Rerank retrieved documents"""

        if not state["retrieved_docs"]:
            return {"reranked_docs": []}

        query = state["current_sub_query"] or state["query"]
        docs = state["retrieved_docs"][:state["retrieval_top_k"]]

        # Extract text for reranking
        texts = [doc["content"] for doc in docs]

        # Rerank
        reranked = await self.rerank.rerank(
            query=query,
            documents=texts,
            top_n=state["rerank_top_n"]
        )

        # Merge scores back to documents
        reranked_docs = []
        for i, (idx, score) in enumerate(reranked):
            doc = docs[idx].copy()
            doc["rerank_score"] = score
            doc["rerank_rank"] = i + 1
            reranked_docs.append(doc)

        return {"reranked_docs": reranked_docs}

    # -------------------------------------------------------------------------
    # GENERATE NODE — Answer with citations
    # -------------------------------------------------------------------------
    async def generate(self, state: RAGState, config: RunnableConfig) -> RAGState:
        """Generate final answer from reranked docs"""

        docs = state["reranked_docs"]
        query = state["query"]
        tenant = await self.tenant_mgr.get_tenant(state["tenant_id"])

        if not docs:
            return {
                "answer": "I don't have enough information to answer this question based on the available documents.",
                "citations": [],
                "confidence_score": 0.0
            }

        # Build context with citations
        context_parts = []
        citations = []

        for i, doc in enumerate(docs):
            citation_id = f"doc_{i}"
            context_parts.append(
                f"[{citation_id}] {doc['content'][:1000]}"
            )
            citations.append(Citation(
                document_id=doc.get("document_id", doc.get("id", citation_id)),
                chunk_text=doc["content"][:500],
                score=doc.get("rerank_score", doc.get("score", 0.0)),
                metadata=doc.get("metadata", {})
            ))

        context = "\n\n".join(context_parts)

        # Generation prompt
        gen_prompt = f"""Answer the question using ONLY the provided context.
Cite sources using [doc_N] format.
If the answer is not in the context, say "I don't have that information."
Be concise and accurate.

Context:
{context}

Question: {query}

Answer:"""

        # Get tenant's default model
        model = tenant.default_llm

        response = await self.llm.chat(
            messages=[
                SystemMessage(content="You are a helpful enterprise assistant. Use only provided context."),
                HumanMessage(content=gen_prompt)
            ],
            model=model,
            temperature=state["generation_params"].get("temperature", 0.1),
            max_tokens=state["generation_params"].get("max_tokens", 2048),
        )

        answer = response.content

        # Calculate confidence based on retrieval scores
        avg_score = sum(d.get("rerank_score", d.get("score", 0)) for d in docs) / len(docs)
        confidence = min(avg_score * 1.2, 1.0)

        return {
            "answer": answer,
            "citations": [c.model_dump() for c in citations],
            "confidence_score": confidence
        }

    # -------------------------------------------------------------------------
    # REFLECT NODE — Self-reflection and quality check
    # -------------------------------------------------------------------------
    async def reflect(self, state: RAGState, config: RunnableConfig) -> RAGState:
        """Evaluate answer quality, decide if more retrieval needed"""

        if state["iterations"] >= state["max_iterations"]:
            return {"iterations": state["iterations"] + 1}

        # Quick completeness check
        answer = state["answer"]
        query = state["query"]

        if "don't have" in answer.lower() or "not in the context" in answer.lower():
            # Try one more retrieval with reformulated query
            needs_more = True
        else:
            # LLM-based reflection
            reflect_prompt = f"""Evaluate if this answer fully addresses the question.
Question: {query}
Answer: {answer}

Issues to check:
- Completeness: Does it answer all parts?
- Accuracy: Is it grounded in citations?
- Clarity: Is it clear and well-structured?

Return JSON: {{"needs_more": true/false, "followup_query": "..." or null}}"""

        response = await self.llm.chat(
            messages=[
                SystemMessage(content="You are a quality evaluator. Return only valid JSON."),
                HumanMessage(content=reflect_prompt)
            ],
            temperature=0.1,
            max_tokens=300
        )

        try:
            result = json.loads(response.content)
            needs_more = result.get("needs_more", False)
            followup = result.get("followup_query")

            if needs_more and followup:
                return {
                    "needs_more_info": True,
                    "sub_queries": state["sub_queries"] + [followup],
                    "current_sub_query": followup,
                    "iterations": state["iterations"] + 1
                }
        except json.JSONDecodeError:
            pass

        return {"iterations": state["iterations"] + 1}

    # -------------------------------------------------------------------------
    # GUARDRAILS NODE — Input/Output validation
    # -------------------------------------------------------------------------
    async def guardrails_check(self, state: RAGState, config: RunnableConfig) -> RAGState:
        """Run guardrails on input query and output answer"""

        if not state.get("enable_guardrails", True):
            return {"guardrails_results": {}, "guardrails_passed": True}

        tenant = await self.tenant_mgr.get_tenant(state["tenant_id"])
        custom_rails = tenant.custom_guardrails

        # Input guardrails
        input_results = await self.guardrails.check_input(
            query=state["query"],
            tenant_id=state["tenant_id"],
            custom_rails=custom_rails
        )

        # Output guardrails (if we have an answer)
        output_results = {}
        if state.get("answer"):
            output_results = await self.guardrails.check_output(
                answer=state["answer"],
                query=state["query"],
                citations=state["citations"],
                tenant_id=state["tenant_id"],
                custom_rails=custom_rails
            )

        all_passed = (
            input_results.get("passed", True) and
            output_results.get("passed", True)
        )

        pii_detected = (
            input_results.get("pii_detected", False) or
            output_results.get("pii_detected", False)
        )

        violations = (
            input_results.get("violations", []) +
            output_results.get("violations", [])
        )

        return {
            "guardrails_results": {
                "input": input_results,
                "output": output_results
            },
            "guardrails_passed": all_passed,
            "pii_detected": pii_detected,
            "safety_violations": violations
        }

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------
    async def _assess_complexity(self, query: str) -> float:
        """Assess query complexity (0-1)"""
        # Simple heuristic
        words = query.split()
        has_multiple_questions = query.count("?") > 1
        has_comparison = any(w in query.lower() for w in ["compare", "versus", "vs", "difference"])
        has_temporal = any(w in query.lower() for w in ["trend", "over time", "history", "evolution"])
        has_multi_hop = any(w in query.lower() for w in ["why", "how", "explain", "cause", "effect"])

        score = min(len(words) / 50, 1.0) * 0.3
        score += 0.2 if has_multiple_questions else 0
        score += 0.2 if has_comparison else 0
        score += 0.15 if has_temporal else 0
        score += 0.15 if has_multi_hop else 0

        return min(score, 1.0)

    async def _hybrid_search(self, query: str, filters: Dict, top_k: int, tenant: TenantConfig) -> List[Dict]:
        """Dense + Sparse + ColBERT hybrid search"""
        # Get embeddings
        dense_vec, sparse_vec = await self.embed.embed_hybrid(query)

        # Search Qdrant
        results = await self.vector.hybrid_search(
            tenant_id=tenant.tenant_id,
            dense_vector=dense_vec,
            sparse_vector=sparse_vec,
            filters=filters,
            limit=top_k,
            with_payload=True
        )
        return results

    async def _dense_search(self, query: str, filters: Dict, top_k: int, tenant: TenantConfig) -> List[Dict]:
        dense_vec = await self.embed.embed_dense(query)
        return await self.vector.dense_search(
            tenant_id=tenant.tenant_id,
            vector=dense_vec,
            filters=filters,
            limit=top_k
        )

    async def _sparse_search(self, query: str, filters: Dict, top_k: int, tenant: TenantConfig) -> List[Dict]:
        sparse_vec = await self.embed.embed_sparse(query)
        return await self.vector.sparse_search(
            tenant_id=tenant.tenant_id,
            sparse_vector=sparse_vec,
            filters=filters,
            limit=top_k
        )

    async def _colbert_search(self, query: str, filters: Dict, top_k: int, tenant: TenantConfig) -> List[Dict]:
        colbert_vecs = await self.embed.embed_colbert(query)
        return await self.vector.colbert_search(
            tenant_id=tenant.tenant_id,
            vectors=colbert_vecs,
            filters=filters,
            limit=top_k
        )