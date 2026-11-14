"""Synthetic CPU-only filtration microbenchmark; NOT a real TiEE gateway benchmark."""
import argparse
import json
import platform
import random
import statistics
import time


def events(n, seed):
    rng = random.Random(seed)
    return [(rng.random() < 0.04, rng.randrange(100)) for _ in range(n)]


def baseline(data):
    return [important or score >= 50 for important, score in data]


def candidate(data):
    return [True if important else score >= 50 for important, score in data]


def percentile(samples, fraction):
    if not samples:
        raise ValueError("empty samples")
    ordered = sorted(samples)
    return ordered[min(len(ordered)-1, int((len(ordered)-1)*fraction + 0.5))]


def evaluate(n=10000, repetitions=7, warmups=2, seed=20261113):
    if n <= 0 or repetitions < 3 or warmups < 0:
        raise ValueError("invalid parameters")
    data = events(n, seed)
    expected = baseline(data)
    measurements = {"baseline": [], "candidate": []}
    for iteration in range(warmups + repetitions):
        methods = [("baseline", baseline), ("candidate", candidate)]
        if iteration % 2:
            methods.reverse()
        for label, method in methods:
            start = time.perf_counter_ns()
            actual = method(data)
            elapsed_ms = (time.perf_counter_ns() - start) / 1e6
            if actual != expected:
                raise AssertionError(f"{label} incorrect")
            if iteration >= warmups:
                measurements[label].append(elapsed_ms)
    return {
        "evidence_type": "local synthetic CPU-only microbenchmark",
        "not_production_evidence": True,
        "parameters": {"n": n, "repetitions": repetitions, "warmups": warmups, "seed": seed},
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "correctness": {
            "equal_outputs": True,
            "important_events": sum(important for important, _ in data),
            "important_dropped": sum(important and not accepted for (important, _), accepted in zip(data, expected))
        },
        "measurements": {
            label: {
                "raw_ms": samples,
                "median_ms": statistics.median(samples),
                "p50_ms": percentile(samples, 0.50),
                "p95_ms": percentile(samples, 0.95),
                "p99_ms": percentile(samples, 0.99)
            } for label, samples in measurements.items()
        },
        "limitations": [
            "Only Python list-processing is measured, not a TiEE gateway",
            "No Redis, Kafka, PostgreSQL, GPU, network or storage measured",
            "No confidence intervals, independent replication or production inference"
        ]
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=10000)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20261113)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.n, args.repetitions, args.warmups, args.seed), indent=2))
