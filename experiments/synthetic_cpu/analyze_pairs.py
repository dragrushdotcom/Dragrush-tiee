import math
import random
import statistics


def paired_summary(baseline, candidate, resamples=1000, seed=20261113):
    baseline, candidate = list(baseline), list(candidate)
    if len(baseline) != len(candidate) or len(baseline) < 3 or isinstance(resamples, bool) or not isinstance(resamples, int) or resamples < 100:
        raise ValueError('invalid paired design')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in baseline + candidate):
        raise ValueError('invalid sample')
    rng = random.Random(seed)
    n = len(baseline)
    def ratio(indices):
        return sum(baseline[i] for i in indices) / sum(candidate[i] for i in indices)
    boots = sorted(ratio([rng.randrange(n) for _ in range(n)]) for _ in range(resamples))
    return {'scope': 'synthetic CPU only', 'production_evidence': False, 'pairs': n, 'ratio': ratio(range(n)), 'bootstrap_95_interval': [boots[int(.025 * resamples)], boots[math.ceil(.975 * resamples) - 1]], 'median_paired_difference_ms': statistics.median(a-b for a,b in zip(baseline,candidate)), 'caveat': 'Within-run uncertainty only; autocorrelation and system noise remain'}
