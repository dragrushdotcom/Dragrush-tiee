"""Matched repeated trials of the real starter processor at two workload settings.

This compares hash-chain iteration costs, NOT TiEE service optimization or
production speedup. No gateway, queue, database, network or GPU is exercised.
"""
import json
import statistics
from measure_processor import measure

def matched(seed=101, count=100, repeats=5, warmups=1, baseline_iterations=0, treatment_iterations=100):
    if baseline_iterations == treatment_iterations:
        raise ValueError("distinct workloads required")
    base = measure(seed=seed, count=count, iterations=baseline_iterations, repeats=repeats, warmups=warmups)
    treat = measure(seed=seed, count=count, iterations=treatment_iterations, repeats=repeats, warmups=warmups)
    if base["fixture_sha256"] != treat["fixture_sha256"] or base["processor_sha256"] != treat["processor_sha256"]:
        raise AssertionError("unmatched source or fixture")
    pairs = []
    for a,b in zip(base["runs"],treat["runs"]):
        pairs.append({"baseline_elapsed_s":a["elapsed_s"],"treatment_elapsed_s":b["elapsed_s"],
                      "elapsed_ratio_treatment_over_baseline":b["elapsed_s"]/a["elapsed_s"]})
    return {"experiment":"same_processor_distinct_hash_workloads",
            "interpretation":"workload sensitivity only; sequential unrandomized order; not an optimization A/B or service speedup",
            "fixture_sha256":base["fixture_sha256"],"processor_sha256":base["processor_sha256"],
            "baseline_iterations":baseline_iterations,"treatment_iterations":treatment_iterations,
            "repeats":repeats,"warmups":warmups,"pairs":pairs,
            "median_elapsed_ratio":statistics.median(p["elapsed_ratio_treatment_over_baseline"] for p in pairs),
            "production_speedup_evidence":False,"service_recovery_evidence":False}

if __name__ == "__main__":
    print(json.dumps(matched(),indent=2,sort_keys=True))
