#!/usr/bin/env python3
# =============================================================================
# EVALUATION — RAGAS evaluation for RAG quality
# =============================================================================
# Usage: python eval.py --tenant acme-corp --dataset eval_data.json
# =============================================================================

import asyncio
import json
import argparse
import aiohttp
from typing import List, Dict, Any
from dataclasses import dataclass
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
    context_relevancy,
    answer_similarity,
    answer_correctness
)
from datasets import Dataset
import pandas as pd


@dataclass
class EvalSample:
    """Single evaluation sample"""
    question: str
    ground_truth: str
    contexts: List[str]
    answer: str


async def get_rag_response(
    session: aiohttp.ClientSession,
    base_url: str,
    tenant_id: str,
    api_key: str,
    question: str
) -> Dict[str, Any]:
    """Get response from RAG API"""
    url = f"{base_url}/v1/generate"
    headers = {
        "Content-Type": "application/json",
        "X-Tenant-ID": tenant_id,
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "query": question,
        "retrieval_strategy": "hybrid",
        "retrieval_top_k": 20,
        "rerank_top_n": 5,
        "enable_guardrails": True,
        "enable_agentic": True
    }

    async with session.post(url, headers=headers, json=payload) as response:
        return await response.json()


async def run_evaluation(
    base_url: str,
    tenant_id: str,
    api_key: str,
    eval_data: List[Dict]
) -> Dict[str, Any]:
    """Run RAGAS evaluation"""

    print(f"Running evaluation on {len(eval_data)} samples...")

    samples = []
    async with aiohttp.ClientSession() as session:
        for i, item in enumerate(eval_data):
            print(f"Processing {i+1}/{len(eval_data)}: {item['question'][:50]}...")

            response = await get_rag_response(session, base_url, tenant_id, api_key, item['question'])

            sample = EvalSample(
                question=item['question'],
                ground_truth=item['ground_truth'],
                contexts=[c['chunk_text'] for c in response.get('citations', [])],
                answer=response.get('answer', '')
            )
            samples.append(sample)

    # Convert to RAGAS dataset
    dataset_dict = {
        "question": [s.question for s in samples],
        "ground_truth": [s.ground_truth for s in samples],
        "contexts": [s.contexts for s in samples],
        "answer": [s.answer for s in samples]
    }

    dataset = Dataset.from_dict(dataset_dict)

    # Run RAGAS evaluation
    print("Running RAGAS metrics...")
    result = evaluate(
        dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
            context_relevancy,
            answer_similarity,
            answer_correctness
        ]
    )

    return result


def main():
    parser = argparse.ArgumentParser(description="RAGAS Evaluation for Enterprise RAG")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL")
    parser.add_argument("--tenant", required=True, help="Tenant ID")
    parser.add_argument("--api-key", required=True, help="API Key")
    parser.add_argument("--dataset", required=True, help="Evaluation dataset JSON file")
    parser.add_argument("--output", help="Output results file")

    args = parser.parse_args()

    # Load evaluation dataset
    with open(args.dataset) as f:
        eval_data = json.load(f)

    # Validate format
    for item in eval_data:
        if 'question' not in item or 'ground_truth' not in item:
            print("Error: Each item must have 'question' and 'ground_truth' fields")
            sys.exit(1)

    print(f"Loaded {len(eval_data)} evaluation samples")

    # Run evaluation
    result = asyncio.run(run_evaluation(
        base_url=args.url,
        tenant_id=args.tenant,
        api_key=args.api_key,
        eval_data=eval_data
    ))

    # Print results
    print("\n" + "="*60)
    print("RAGAS EVALUATION RESULTS")
    print("="*60)
    for metric, score in result.items():
        print(f"  {metric}: {score:.4f}")
    print("="*60)

    # Save results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump({k: float(v) for k, v in result.items()}, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()