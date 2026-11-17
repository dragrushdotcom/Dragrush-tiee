"""Matched local starter-processor trial; NOT a deployed TiEE service benchmark.

Baseline decodes each envelope on the processing path. Treatment decodes the
same envelopes in a separate preparation phase. BOTH phases are timed; the
treatment must not hide preparation costs. This tests batching only.
"""
import argparse
import hashlib
import json
import platform
import statistics
import time
from benchmark.generator import generate
from shared.processor import canonical, decode, eligible, process


def baseline(raws, iterations):
    outputs = []
    for raw in raws:
        event = decode(raw)
        if eligible(event):
            outputs.append(process(event, iterations))
    return outputs


def treatment(raws, iterations):
    decoded = [decode(raw) for raw in raws]
    return [process(event, iterations) for event in decoded if eligible(event)]


def measure(count=100, repetitions=7, warmups=2, iterations=37, seed=101):
    if count <= 0 or count % 100 or repetitions < 3 or warmups < 0:
        raise ValueError("invalid trial configuration")
    raws = [canonical(item["event"]) for item in generate(seed=seed, count=count)]
    expected = baseline(raws, iterations)
    samples = {"baseline": [], "treatment": []}
    for trial in range(warmups + repetitions):
        order = (("baseline", baseline), ("treatment", treatment))
        if trial % 2:
            order = tuple(reversed(order))
        for label, function in order:
            start = time.perf_counter_ns()
            observed = function(raws, iterations)
            elapsed = time.perf_counter_ns() - start
            if observed != expected:
                raise AssertionError("processor output mismatch")
            if trial >= warmups:
                samples[label].append(elapsed)
    return {
        "scope": "actual starter processor, local in-process only",
        "service_evidence": False,
        "production_speedup_claim": False,
        "seed": seed, "count": count, "iterations": iterations,
        "warmups": warmups, "repetitions": repetitions,
        "input_sha256": hashlib.sha256(b"".join(raws)).hexdigest(),
        "output_sha256": hashlib.sha256(canonical(expected)).hexdigest(),
        "python": platform.python_version(),
        "measurements_ns": samples,
        "median_ns": {key: statistics.median(value) for key, value in samples.items()},
        "limitations": ["No gateway, network, Redis, Kafka, or PostgreSQL",
                        "Local paired timings are not independent production trials",
                        "No deployed-service failure/recovery experiment"]
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--iterations", type=int, default=37)
    args = parser.parse_args()
    print(json.dumps(measure(args.count, args.repetitions, args.warmups, args.iterations), indent=2))
