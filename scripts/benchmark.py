"""
PhishGuardAI Performance Benchmark

Measures latency and throughput for different request paths.
"""

import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import requests

GATEWAY_URL = "http://localhost:8000/predict"

test_cases = [
    ("https://google.com", "whitelist"),
    ("https://phishing.top", "high_confidence_block"),
    ("https://example.com", "low_confidence_allow"),
    ("https://npm.org", "short_domain_judge"),
]


def test_latency(url, label, n=100):
    """Measure latency for a single URL"""
    latencies = []
    errors = 0

    for _ in range(n):
        try:
            start = time.time()
            response = requests.post(GATEWAY_URL, json={"url": url}, timeout=5)
            response.raise_for_status()
            latencies.append((time.time() - start) * 1000)  # Convert to ms
        except Exception:
            errors += 1

    if not latencies:
        return {"label": label, "url": url, "error": "All requests failed"}

    return {
        "label": label,
        "url": url,
        "n": n,
        "errors": errors,
        "p50": statistics.median(latencies),
        "p95": (
            statistics.quantiles(latencies, n=20)[18]
            if len(latencies) > 20
            else max(latencies)
        ),
        "p99": (
            statistics.quantiles(latencies, n=100)[98]
            if len(latencies) > 100
            else max(latencies)
        ),
        "mean": statistics.mean(latencies),
        "min": min(latencies),
        "max": max(latencies),
    }


def test_throughput(n_requests=1000, n_workers=10):
    """Measure throughput with concurrent requests"""

    def make_request(_):
        try:
            response = requests.post(
                GATEWAY_URL, json={"url": "https://example.com"}, timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False

    start = time.time()
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        results = list(executor.map(make_request, range(n_requests)))
    elapsed = time.time() - start

    success_rate = sum(results) / len(results)
    throughput = n_requests / elapsed

    return {
        "n_requests": n_requests,
        "n_workers": n_workers,
        "elapsed_seconds": elapsed,
        "throughput_req_per_sec": throughput,
        "success_rate": success_rate,
    }


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("PhishGuardAI - Performance Benchmark")
    print("=" * 70)

    print("\n1. LATENCY TESTS (100 requests per path)")
    print("-" * 70)

    latency_results = []
    for url, label in test_cases:
        print(f"\nTesting: {label}")
        result = test_latency(url, label, n=100)
        latency_results.append(result)

        if "error" in result:
            print(f"  ❌ ERROR: {result['error']}")
        else:
            print("  ✅ SUCCESS")
            print(f"     p50: {result['p50']:6.2f}ms")
            print(f"     p95: {result['p95']:6.2f}ms")
            print(f"     p99: {result['p99']:6.2f}ms")
            print(f"    mean: {result['mean']:6.2f}ms")
            if result["errors"] > 0:
                print(f"  errors: {result['errors']}/{result['n']}")

    print("\n\n2. THROUGHPUT TEST (1000 requests, 10 concurrent workers)")
    print("-" * 70)

    throughput_result = test_throughput(n_requests=1000, n_workers=10)
    print(f"  Throughput: {throughput_result['throughput_req_per_sec']:7.2f} req/sec")
    print(f"  Success Rate: {throughput_result['success_rate'] * 100:5.1f}%")
    print(f"  Total Time: {throughput_result['elapsed_seconds']:7.2f}s")

    print("\n\n3. SUMMARY - PRODUCTION READINESS")
    print("=" * 70)

    # Check against targets
    targets = {
        "whitelist_p95": 10,  # ms
        "model_p95": 50,  # ms
        "judge_p95": 100,  # ms
        "throughput": 100,  # req/sec
        "success_rate": 0.99,  # 99%
    }

    whitelist_result = next(
        (r for r in latency_results if r["label"] == "whitelist"), None
    )
    model_result = next(
        (r for r in latency_results if r["label"] == "low_confidence_allow"), None
    )
    judge_result = next(
        (r for r in latency_results if r["label"] == "short_domain_judge"), None
    )

    print("\nLatency Targets:")
    if whitelist_result and "p95" in whitelist_result:
        status = "✅" if whitelist_result["p95"] < targets["whitelist_p95"] else "⚠️"
        target_ms = targets["whitelist_p95"]
        print(
            f"  {status} Whitelist p95: {whitelist_result['p95']:.2f}ms "
            f"(target: <{target_ms}ms)"
        )

    if model_result and "p95" in model_result:
        status = "✅" if model_result["p95"] < targets["model_p95"] else "⚠️"
        target_ms = targets["model_p95"]
        print(
            f"  {status} Model p95: {model_result['p95']:.2f}ms "
            f"(target: <{target_ms}ms)"
        )

    if judge_result and "p95" in judge_result:
        status = "✅" if judge_result["p95"] < targets["judge_p95"] else "⚠️"
        target_ms = targets["judge_p95"]
        print(
            f"  {status} Judge p95: {judge_result['p95']:.2f}ms "
            f"(target: <{target_ms}ms)"
        )

    print("\nThroughput Targets:")
    status = (
        "✅"
        if throughput_result["throughput_req_per_sec"] > targets["throughput"]
        else "⚠️"
    )
    throughput_val = throughput_result["throughput_req_per_sec"]
    target_throughput = targets["throughput"]
    print(
        f"  {status} Throughput: {throughput_val:.2f} req/sec "
        f"(target: >{target_throughput} req/sec)"
    )

    status = (
        "✅" if throughput_result["success_rate"] > targets["success_rate"] else "⚠️"
    )
    success_pct = throughput_result["success_rate"] * 100
    target_pct = targets["success_rate"] * 100
    print(f"  {status} Success Rate: {success_pct:.1f}% (target: >{target_pct:.0f}%)")

    print("\n" + "=" * 70)
    print("Benchmark Complete!")
    print("=" * 70)
