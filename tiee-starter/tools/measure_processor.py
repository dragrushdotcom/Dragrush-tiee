"""Measure the actual TiEE starter hash-chain processor, not synthetic list filtering.

Run from repository root: python3 tiee-starter/tools/measure_processor.py
Output is JSON on stdout; no database, broker, gateway, or GPU is exercised.
"""
import hashlib
import json
import platform
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.generator import generate
from shared.processor import decode, eligible, process, canonical

def percentile(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered)-1, max(0, int((len(ordered)-1)*q)))]

def measure(seed=101, count=100, iterations=100, repeats=5, warmups=1):
    if type(repeats) is not int or repeats < 3 or type(warmups) is not int or warmups < 1:
        raise ValueError("at least three repeats and one warmup required")
    if type(iterations) is not int or not 0 <= iterations <= 10000:
        raise ValueError("invalid processor iterations")
    fixtures = [canonical(x["event"]) for x in generate(seed=seed, count=count, useful_percent=50)]
    fixture_hash = hashlib.sha256(b"".join(len(x).to_bytes(4,"big")+x for x in fixtures)).hexdigest()
    results = []
    for trial in range(warmups+repeats):
        raw = []
        accepted = 0
        start = time.perf_counter_ns()
        for payload in fixtures:
            t0 = time.perf_counter_ns()
            event = decode(payload)
            if eligible(event):
                output = process(event, iterations)
                if output["event_id"] != event["event_id"] or len(output["digest"]) != 64:
                    raise AssertionError("processor output invalid")
                accepted += 1
            raw.append((time.perf_counter_ns()-t0)/1e6)
        duration = (time.perf_counter_ns()-start)/1e9
        if accepted != count//2:
            raise AssertionError("unexpected eligible count")
        if trial >= warmups:
            results.append({"elapsed_s":duration,"p50_ms":percentile(raw,.50),
                            "p95_ms":percentile(raw,.95),"p99_ms":percentile(raw,.99),
                            "throughput_events_s":count/duration,"eligible":accepted})
    return {"component":"tiee-starter/shared/processor.py","mode":"in_process_cpu",
            "not_gateway_or_queue_or_db":True,"no_baseline_comparison":True,
            "production_speedup_evidence":False,"seed":seed,"count":count,
            "iterations":iterations,"warmups":warmups,"repeats":repeats,
            "fixture_sha256":fixture_hash,"python":platform.python_version(),
            "processor_sha256":hashlib.sha256((ROOT/"shared"/"processor.py").read_bytes()).hexdigest(),
            "runs":results,"median_throughput_events_s":statistics.median(x["throughput_events_s"] for x in results)}

if __name__ == "__main__":
    print(json.dumps(measure(),sort_keys=True,indent=2))
