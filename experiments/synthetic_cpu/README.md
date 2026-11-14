# Synthetic CPU baseline — experimental protocol

This is a **controlled, synthetic Python microbenchmark**, not a benchmark of the deployed TiEE system. The repository main HEAD inspected was `1d5edba143628854df52a5d8bc6c8d4b380e458a`. The actual gateway/EV/queue implementations and historic v4.4/v4.5 benchmark artifacts were **not established from inspected source**. No architecture components are presumed to be running.

## Falsifiable hypothesis
A candidate filtration expression returns exactly the same accept/reject decisions as the reference implementation on fixed seeded events. The purpose is to establish a reproducible measurement protocol, **not** to claim performance superiority. Every important event must be accepted even if its numeric score is low.

## Reproduce
```sh
cd experiments/synthetic_cpu
python -m unittest -v test_benchmark.py
python benchmark.py --n 10000 --repetitions 7 --warmups 2 --seed 20261113 > result.json
```

No third-party packages or credentials are required. The benchmark alternates baseline/candidate order, uses identical input, and reports raw per-run wall-clock samples plus median/p50/p95/p99 in milliseconds. Warmup samples are excluded. The `important_dropped` metric must be zero.

## Interpretation and controls
Results are noisy local Python process timings and cannot establish TiEE latency, throughput, GPU utilization, EV filtration effectiveness, or production performance. Do not compare these numbers to historic v4.4/v4.5 claims. Next experiment: identify real TiEE executable components and their workloads, pin environment and baseline SHA, add repeat runs with confidence intervals and end-to-end correctness/false-negative metrics. Do not merge until CI validates this branch.

## Advisory reasoning
Recommended intensity: **HIGH** — experimental validity and component provenance are uncertain. No model configuration change is implied. No production actions or costs.
