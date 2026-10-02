# Verification record

This package was tested in the authoring environment with:

```sh
python3 -m unittest discover -s tests -v
python3 -m benchmark --out results/verified-foundation --count 300 --iterations 100
```

Outcome: 25 automated tests passed. The functional run passed all nine comparisons (three traffic mixes across B0, B1, and T function paths). Each mix offered 300 unique events to each path.

| Useful mix | Correct useful outputs per path | B0 processing calls | B1 processing calls | T processing calls |
|---|---:|---:|---:|---:|
| 100% | 300 | 300 | 300 | 300 |
| 50% | 150 | 300 | 150 | 150 |
| 10% | 30 | 300 | 30 | 30 |

All nine comparisons found zero missing, unexpected, wrong, or duplicate output rows. The automated tests also deliberately introduce those errors and require the evaluator to detect them. The CLI test verifies output overwrite refusal and evidence checksums.

These results establish only offline function-level consistency on the synthetic task. Processing-call counts are not timing results. They do not establish speedup, CPU savings, authorization safety, durability, queueing behavior, fault recovery, or independent reproduction. See results/verified-foundation/summary.json for the actual runtime, source hashes, and machine-readable results.
