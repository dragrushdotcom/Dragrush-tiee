"""Reproducible synthetic paired-run receipt; not TiEE component evidence."""
import argparse
import json
from pathlib import Path
from benchmark import evaluate
from analyze_pairs import paired_summary


def receipt(n=10000, repetitions=9, warmups=2, seed=20261113):
    result = evaluate(n=n, repetitions=repetitions, warmups=warmups, seed=seed)
    baseline = result['measurements']['baseline']['raw_ms']
    candidate = result['measurements']['candidate']['raw_ms']
    if len(baseline) != len(candidate) or len(baseline) < 3:
        raise AssertionError('incomplete paired measurements')
    result['paired_analysis'] = paired_summary(baseline, candidate, seed=seed)
    result['paired_analysis']['pairing'] = 'same iteration, alternating method order'
    result['paired_analysis']['scope'] = 'synthetic CPU-only Python list processing'
    result['paired_analysis']['production_evidence'] = False
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=10000)
    parser.add_argument('--repetitions', type=int, default=9)
    parser.add_argument('--warmups', type=int, default=2)
    parser.add_argument('--seed', type=int, default=20261113)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    content = json.dumps(receipt(args.n, args.repetitions, args.warmups, args.seed), indent=2) + '\n'
    if args.output:
        args.output.write_text(content, encoding='utf-8')
    else:
        print(content, end='')
