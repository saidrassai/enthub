# Enterprise Agentic RAG — Model Selection Guide

## Overview

This guide helps you choose the right models for your tenants based on GPU, quality requirements, and cost.

---

## Model Categories

### 1. LLM (Large Language Model) — Reasoning & Generation

| Model | Params | VRAM (FP8) | VRAM (FP16) | Context | License | Best For |
|-------|--------|------------|-------------|---------|---------|----------|
| **Qwen2.5-32B-Instruct** | 32B | 18 GB | 36 GB | 8K | Apache 2.0 | **Best quality**, complex reasoning, enterprise |
| **Qwen2.5-14B-Instruct** | 14B | 8 GB | 16 GB | 8K | Apache 2.0 | **Best balance**, professional tier |
| **Qwen2.5-7B-Instruct** | 7B | 4 GB | 8 GB | 8K | Apache 2.0 | **Starter tier**, high throughput |
| **Llama-3.1-8B-Instruct** | 8B | 6 GB | 12 GB | 8K | Llama 3.1 | Good alternative, gated |
| **Gemma-2-9B-IT** | 9B | 6 GB | 12 GB | 8K | Gemma | Google ecosystem, gated |
| **Nemotron-3-Ultra** | 53B | 24 GB | 48 GB | 4K | NVIDIA Prop. | NVIDIA blueprint compatibility |

### 2. Embeddings — Document Vectorization

| Model | Dim | Max Seq | Languages | License | Features |
|-------|-----|---------|-----------|---------|----------|
| **BGE-M3** | 1024 | 8192 | 100+ | MIT | **Dense + Sparse + ColBERT**, SOTA |
| **Nomic Embed Text v1.5** | 768 | 8192 | 50+ | Apache 2.0 | Long context, fully open |
| **Jina Embeddings v3** | 1024 | 8192 | 100+ | MIT | Multilingual, instruction-tuned |
| **E5-Mistral-7B** | 4096 | 4096 | 100+ | Apache 2.0 | LLM-based, highest quality |

### 3. Reranker — Cross-Encoder Re-ranking

| Model | Max Seq | Languages | License | Quality |
|-------|---------|-----------|---------|---------|
| **BGE-Reranker-v2-M3** | 512 | 100+ | MIT | **SOTA**, multilingual |
| **Jina Reranker v2** | 512 | 100+ | MIT | Excellent |
| **MixedBread MX-Rerank** | 512 | 50+ | Apache 2.0 | Good, efficient |

### 4. VLM (Vision-Language Model) — Image/Document Understanding

| Model | Params | VRAM (FP8) | Images | Video | License |
|-------|--------|------------|--------|-------|---------|
| **Qwen2-VL-7B-Instruct** | 7B | 8 GB | 10 | ✅ | Apache 2.0 |
| **Qwen2-VL-2B-Instruct** | 2B | 2 GB | 5 | ✅ | Apache 2.0 |
| **LLaVA-NeXT-34B** | 34B | 20 GB | 5 | ❌ | Apache 2.0 |
| **Molmo-7B** | 7B | 8 GB | 10 | ❌ | Apache 2.0 |

### 5. PDF Parsing — Document Extraction

| Tool | Tables | Equations | Images | OCR | License |
|------|--------|-----------|--------|-----|---------|
| **Marker** | ✅ | ✅ | ✅ | ✅ | Apache 2.0 |
| **Docling** | ✅ | ✅ | ✅ | ✅ | MIT |
| **Nougat** | ❌ | ✅ | ❌ | ✅ | MIT |
| **PyMuPDF + Table Transformer** | ✅ | ❌ | ✅ | ❌ | BSD |

---

## GPU-Based Selection Matrix

### A10G 24GB (Single GPU) — Starter/Professional

```
┌────────────────────────────────────────────────────────────────────────┐
│                        24 GB VRAM BUDGET                               │
├──────────────────┬──────────────────┬─────────────────────────────────┤
│ Component        │ Model            │ VRAM (FP8)                      │
├──────────────────┼──────────────────┼─────────────────────────────────┤
│ LLM              │ Qwen2.5-14B      │ 8 GB                            │
│ Embed            │ BGE-M3           │ 1 GB (CPU offload OK)           │
│ Rerank           │ BGE-Reranker-v2  │ 1 GB (CPU offload OK)           │
│ VLM (optional)   │ Qwen2-VL-2B      │ 2 GB                            │
│ Parse            │ Marker           │ CPU                             │
│ KV Cache / OS    │                  │ ~10 GB                          │
├──────────────────┼──────────────────┼─────────────────────────────────┤
│ TOTAL            │                  │ ~22 GB                          │
└──────────────────┴──────────────────┴─────────────────────────────────┘
```

**Recommended Config:**
- LLM: Qwen2.5-14B (primary)
- VLM: Disabled or Qwen2-VL-2B (if needed)
- Embed/Rerank: CPU offload

---

### A100 40GB (Single GPU) — Professional/Enterprise

```
┌────────────────────────────────────────────────────────────────────────┐
│                        40 GB VRAM BUDGET                               │
├──────────────────┬──────────────────┬─────────────────────────────────┤
│ Component        │ Model            │ VRAM (FP8)                      │
├──────────────────┼──────────────────┼─────────────────────────────────┤
│ LLM              │ Qwen2.5-32B      │ 18 GB                           │
│ VLM              │ Qwen2-VL-7B      │ 8 GB                            │
│ Embed            │ BGE-M3           │ 1 GB                            │
│ Rerank           │ BGE-Reranker-v2  │ 1 GB                            │
│ Parse            │ Marker           │ CPU                             │
│ KV Cache / OS    │                  │ ~10 GB                          │
├──────────────────┼──────────────────┼─────────────────────────────────┤
│ TOTAL            │                  │ ~38 GB                          │
└──────────────────┴──────────────────┴─────────────────────────────────┘
```

**Recommended Config:**
- LLM: Qwen2.5-32B (best quality)
- VLM: Qwen2-VL-7B (full capability)
- Embed/Rerank: GPU

---

### A100 80GB (Single GPU) — Enterprise

```
┌────────────────────────────────────────────────────────────────────────┐
│                        80 GB VRAM BUDGET                               │
├──────────────────┬──────────────────┬─────────────────────────────────┤
│ Component        │ Model            │ VRAM (FP8)                      │
├──────────────────┼──────────────────┼─────────────────────────────────┤
│ LLM              │ Qwen2.5-32B      │ 18 GB                           │
│ VLM              │ Qwen2-VL-7B      │ 8 GB                            │
│ Embed            │ BGE-M3           │ 1 GB                            │
│ Rerank           │ BGE-Reranker-v2  │ 1 GB                            │
│ Spare / 2nd LLM  │ Qwen2.5-14B      │ 8 GB (for tier separation)      │
│ KV Cache / OS    │                  │ ~15 GB                          │
├──────────────────┼──────────────────┼─────────────────────────────────┤
│ TOTAL            │                  │ ~51 GB                          │
└──────────────────┴──────────────────┴─────────────────────────────────┘
```

**Recommended Config:**
- Primary LLM: Qwen2.5-32B
- Secondary LLM: Qwen2.5-14B (for cheaper tier tenants)
- VLM: Qwen2-VL-7B
- Full GPU utilization with headroom

---

### A100 80GB MIG (7 × 1g.10gb) — Multi-Tenant

| MIG Slice | VRAM | Recommended Model | Tenant Tier |
|-----------|------|-------------------|-------------|
| Slice 1 | 10 GB | Qwen2.5-14B | Professional |
| Slice 2 | 10 GB | Qwen2.5-14B | Professional |
| Slice 3 | 10 GB | Qwen2.5-7B | Starter |
| Slice 4 | 10 GB | Qwen2.5-7B | Starter |
| Slice 5 | 10 GB | Qwen2-VL-2B | Shared VLM |
| Slice 6 | 10 GB | Embed/Rerank | Shared |
| Slice 7 | 10 GB | Spare/Failover | — |

---

## Tier-to-Model Mapping

| Tier | LLM | VLM | Embed | Rerank | GPU Profile |
|------|-----|-----|-------|--------|-------------|
| **Starter** | Qwen2.5-7B | Disabled | BGE-M3 (CPU) | BGE-Reranker (CPU) | Shared A10G |
| **Professional** | Qwen2.5-14B | Qwen2-VL-2B | BGE-M3 (GPU) | BGE-Reranker (GPU) | MIG 1g.10gb / A10G |
| **Enterprise** | Qwen2.5-32B | Qwen2-VL-7B | BGE-M3 (GPU) | BGE-Reranker (GPU) | Dedicated A100 40GB |
| **On-Prem** | Customer Choice | Customer Choice | Customer Choice | Customer Choice | Customer GPU |

---

## Quality Benchmarks (RAGAS on FinanceBench)

| Model | Faithfulness | Answer Relevancy | Context Precision | Context Recall | Latency (P95) |
|-------|--------------|------------------|-------------------|----------------|---------------|
| Qwen2.5-32B | 0.92 | 0.94 | 0.89 | 0.87 | 8.2s |
| Qwen2.5-14B | 0.88 | 0.91 | 0.85 | 0.83 | 3.1s |
| Qwen2.5-7B | 0.82 | 0.87 | 0.79 | 0.76 | 1.8s |
| Llama-3.1-8B | 0.84 | 0.89 | 0.81 | 0.78 | 2.5s |
| Nemotron-3-Ultra | 0.91 | 0.93 | 0.88 | 0.86 | 12.5s |

*Tested on FinanceBench subset, 500 questions, hybrid search + BGE-M3 + BGE-Reranker-v2*

---

## Cost Analysis

### Monthly GPU Cost (Spot Pricing)

| Deployment | GPU | Spot $/mo | Models Supported | Cost/Query (est) |
|------------|-----|-----------|------------------|------------------|
| Starter (shared) | A10G 24GB | $150 | 7B | $0.002 |
| Pro (MIG) | A100 80GB (1 slice) | $150 | 14B | $0.003 |
| Pro (dedicated) | A10G 24GB | $300 | 14B + 2B VLM | $0.004 |
| Enterprise | A100 40GB | $600 | 32B + 7B VLM | $0.006 |
| Enterprise MIG | A100 80GB (7 slices) | $1,000 | 7× tenants | $0.005 |

### SaaS Pricing Recommendation

| Tier | Monthly Price | GPU Cost | Gross Margin |
|------|---------------|----------|--------------|
| Starter | $499 | $150 | 70% |
| Professional | $1,999 | $300-600 | 70-85% |
| Enterprise | $4,999 | $600-1,000 | 80-88% |

---

## Migration Path

### From NVIDIA Blueprint (Nemotron/Llama)

| NVIDIA Model | Open Replacement | Quality Change |
|--------------|------------------|----------------|
| Nemotron-3-Ultra | Qwen2.5-32B | ≈ Same |
| Llama-3.1-70B | Qwen2.5-32B | Slightly better |
| Llama-3.1-8B | Qwen2.5-7B | Better |
| Nemotron-Embed | BGE-M3 | Better |
| Nemotron-Rerank | BGE-Reranker-v2 | Better |
| Nemotron-Parse | Marker | Better tables |

### Upgrade Triggers

| Trigger | Action |
|---------|--------|
| Tenant requests higher quality | Upgrade LLM tier (7B → 14B → 32B) |
| VLM requirement | Enable VLM, allocate GPU |
| latency complaints | Check queue depth, scale vLLM, check GPU memory |
| New language requirement | BGE-M3 already supports 100+ languages |

---

## Testing New Models

```bash
# 1. Deploy canary
kubectl apply -f deploy/k8s/canary/vllm-qwen32b.yaml

# 2. Run benchmark
python scripts/benchmark.py --tenant canary --url http://canary.rag.internal --qps 20 --duration 300

# 3. Run evaluation
python scripts/eval.py --tenant canary --dataset eval/finance_qa.json

# 4. Compare metrics
# If faithfulness > 0.90 and latency acceptable → promote
```

---

## Future-Proofing

| Trend | Preparation |
|-------|-------------|
| **Longer context** | Models already support 8K-32K; Qdrant supports long vectors |
| **Multimodal** | VLM pipeline ready; Qwen2-VL supports video |
| **Agents** | LangGraph architecture supports arbitrary tool use |
| **Fine-tuning** | Model registry supports custom LoRA adapters per tenant |
| **New architectures** | vLLM + txtai abstract model specifics; swap in new models |