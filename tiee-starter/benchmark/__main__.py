"""Run offline functional checks; no timing or throughput claims."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

from .generator import generate, encoded
from .oracle import expected, reconcile
from shared.processor import canonical, decode, eligible, ev, process


def write_json(path, value):
    path.write_bytes(encoded(value) + b"\n")


def write_lines(path, rows):
    with path.open("xb") as f:
        for row in rows:
            f.write(encoded(row) + b"\n")


def check(mix, seed, count, iterations, rate):
    records = list(generate(seed, count, mix, rate))
    truth = expected(records, iterations)
    arm_reports = {}
    outputs = {}
    decisions = {}
    for arm in ("B0", "B1", "T"):
        rows, audit, work = [], [], 0
        for record in records:
            event = decode(canonical(record["event"]))
            if arm == "B0":
                result = process(event, iterations)
                work += 1
            allow = eligible(event)
            decision = ev(event) if arm == "T" else {
                "disposition": "ALLOW" if allow else "REJECT",
                "reason": "QUALITY_ELIGIBLE" if allow else "QUALITY_BELOW_THRESHOLD"}
            if arm != "B0" and decision["disposition"] == "ALLOW":
                result = process(event, iterations)
                work += 1
            if decision["disposition"] == "ALLOW":
                rows.append(result)
            audit.append({"event_id": event["event_id"], **decision})
        report = reconcile(truth, rows)
        report["processing_calls"] = work
        report["decisions"] = len(audit)
        arm_reports[arm] = report
        outputs[arm], decisions[arm] = rows, audit
    return records, truth, outputs, decisions, arm_reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="new directory; never overwrite")
    parser.add_argument("--count", type=int, default=300)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--rate", type=int, default=10)
    args = parser.parse_args()
    # Validate before creating output; each case is small by design here.
    if not 100 <= args.count <= 10000:
        parser.error("count must be 100..10000")
    list(generate(args.seed, 100, 50, args.rate))
    if args.count % 100 or not 0 <= args.iterations <= 10000:
        parser.error("count must be divisible by 100; iterations must be 0..10000")
    args.out.mkdir(parents=True, exist_ok=False)
    reports = {}
    for mix in (100, 50, 10):
        case = args.out / f"useful-{mix}"
        case.mkdir()
        records, truth, outputs, decisions, report = check(mix, args.seed, args.count, args.iterations, args.rate)
        wire = case / "workload"
        private = case / "evaluator-only"
        wire.mkdir(); private.mkdir()
        write_lines(wire / "requests.jsonl", records)
        write_lines(private / "expected.jsonl", truth)
        for arm in outputs:
            write_lines(case / f"{arm}-outputs.jsonl", outputs[arm])
            write_lines(case / f"{arm}-decisions.jsonl", decisions[arm])
        write_json(case / "correctness.json", report)
        reports[str(mix)] = report
    source = Path(__file__).resolve().parents[1]
    source_hashes = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for folder in ("shared", "benchmark", "storage", "tests")
                     for p in sorted((source / folder).rglob("*.py"))}
    summary = {"stage": "offline-functional-foundation", "benchmark_executed": False,
               "durability_tested": False, "performance_claim": None,
               "python": sys.version, "platform": platform.platform(),
               "config": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
               "source_sha256": source_hashes, "cases": reports,
               "not_implemented": ["HTTP", "PostgreSQL", "Redpanda", "B2", "B3", "scheduled load", "recovery"],
               "pass": all(r["pass"] for case in reports.values() for r in case.values())}
    write_json(args.out / "summary.json", summary)
    sums = [(str(p.relative_to(args.out)), hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(args.out.rglob("*")) if p.is_file()]
    (args.out / "checksums.sha256").write_text("".join(f"{digest}  {name}\n" for name, digest in sums))
    print(json.dumps({"pass": summary["pass"], "stage": summary["stage"], "out": str(args.out)}))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
