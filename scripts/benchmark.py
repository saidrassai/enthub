#!/usr/bin/env python3
# =============================================================================
# BENCHMARK — Load testing for RAG API
# =============================================================================
# Usage: python benchmark.py --tenant acme-corp --qps 50 --duration 300
# =============================================================================

import asyncio
import aiohttp
import argparse
import time
import statistics
import json
from dataclasses import dataclass
from typing import List
import sys


@dataclass
class BenchmarkResult:
    total_requests: int
    successful: int
    failed: int
    latencies: List[float]
    start_time: float
    end_time: float


async def make_request(session: aiohttp.ClientSession, url: str, headers: dict, payload: dict) -> tuple:
    """Make single request, return (success, latency, status)"""
    start = time.perf_counter()
    try:
        async with session.post(url, headers=headers, json=payload) as response:
            await response.json()
            latency = time.perf_counter() - start
            return response.status == 200, latency, response.status
    except Exception as e:
        latency = time.perf_counter() - start
        return False, latency, str(e)


async def worker(
    session: aiohttp.ClientSession,
    url: str,
    headers: dict,
    payload: dict,
    qps: float,
    duration: float,
    results: list
):
    """Worker that sends requests at specified QPS"""
    interval = 1.0 / qps
    start = time.time()
    request_id = 0

    while time.time() - start < duration:
        request_start = time.time()
        success, latency, status = await make_request(session, url, headers, payload)
        results.append((success, latency, status))

        # Rate limiting
        elapsed = time.time() - request_start
        sleep_time = max(0, interval - elapsed)
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)

        request_id += 1


async def run_benchmark(
    base_url: str,
    tenant_id: str,
    api_key: str,
    qps: int,
    duration: int,
    concurrency: int
) -> BenchmarkResult:
    """Run benchmark with specified parameters"""

    url = f"{base_url}/v1/generate"
    headers = {
        "Content-Type": "application/json",
        "X-Tenant-ID": tenant_id,
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "query": "What are the key financial highlights from the latest quarterly report?",
        "retrieval_strategy": "hybrid",
        "retrieval_top_k": 20,
        "rerank_top_n": 5,
        "enable_guardrails": True,
        "enable_agentic": True
    }

    print(f"Starting benchmark: {qps} QPS for {duration}s with {concurrency} workers")
    print(f"Target: {url}")

    per_worker_qps = qps / concurrency
    per_worker_duration = duration

    results = []
    async with aiohttp.ClientSession() as session:
        tasks = [
            worker(session, url, headers, payload, per_worker_qps, per_worker_duration, results)
            for _ in range(concurrency)
        ]
        await asyncio.gather(*tasks)

    # Calculate results
    latencies = [r[1] for r in results]
    successful = sum(1 for r in results if r[0])
    failed = len(results) - successful

    return BenchmarkResult(
        total_requests=len(results),
        successful=successful,
        failed=failed,
        latencies=latencies,
        start_time=time.time(),
        end_time=time.time()
    )


def print_results(result: BenchmarkResult):
    """Print benchmark results"""
    latencies = result.latencies

    print("\n" + "="*60)
    print("BENCHMARK RESULTS")
    print("="*60)
    print(f"Total Requests:  {result.total_requests}")
    print(f"Successful:      {result.successful}")
    print(f"Failed:          {result.failed}")
    print(f"Success Rate:    {result.successful/result.total_requests*100:.2f}%")
    print(f"Actual QPS:      {result.total_requests/(result.end_time-result.start_time):.2f}")
    print()
    print("Latency (seconds):")
    print(f"  Min:           {min(latencies):.4f}")
    print(f"  Max:           {max(latencies):.4f}")
    print(f"  Mean:          {statistics.mean(latencies):.4f}")
    print(f"  Median:        {statistics.median(latencies):.4f}")
    print(f"  P50:           {statistics.quantiles(latencies, n=100)[49]:.4f}")
    print(f"  P90:           {statistics.quantiles(latencies, n=100)[89]:.4f}")
    print(f"  P95:           {statistics.quantiles(latencies, n=100)[94]:.4f}")
    print(f"  P99:           {statistics.quantiles(latencies, n=100)[98]:.4f}")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(description="RAG API Load Benchmark")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL")
    parser.add_argument("--tenant", required=True, help="Tenant ID")
    parser.add_argument("--api-key", required=True, help="API Key")
    parser.add_argument("--qps", type=int, default=50, help="Target QPS")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent workers")
    parser.add_argument("--output", help="Output JSON file")

    args = parser.parse_args()

    result = asyncio.run(run_benchmark(
        base_url=args.url,
        tenant_id=args.tenant,
        api_key=args.api_key,
        qps=args.qps,
        duration=args.duration,
        concurrency=args.concurrency
    ))

    print_results(result)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump({
                "total_requests": result.total_requests,
                "successful": result.successful,
                "failed": result.failed,
                "success_rate": result.successful/result.total_requests,
                "latencies": result.latencies,
                "percentiles": {
                    "p50": statistics.quantiles(result.latencies, n=100)[49],
                    "p90": statistics.quantiles(result.latencies, n=100)[89],
                    "p95": statistics.quantiles(result.latencies, n=100)[94],
                    "p99": statistics.quantiles(result.latencies, n=100)[98]
                }
            }, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()