"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import comb
from numbers import Integral

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    counts = dict.fromkeys(("tp", "fp", "fn", "tn"), 0)
    for h, j in zip(human, judge, strict=True):
        if h not in ("PASS", "FAIL") or j not in ("PASS", "FAIL"):
            raise ValueError("labels must be PASS or FAIL")
        if j == POS:
            counts["tp" if h == POS else "fp"] += 1
        else:
            counts["fn" if h == POS else "tn"] += 1
    return counts


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    tp = cm["tp"]
    predicted, actual = tp + cm["fp"], tp + cm["fn"]
    return tp / predicted if predicted else 0.0, tp / actual if actual else 0.0


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    cm = confusion(human, judge)
    n = sum(cm.values())
    actual, predicted = cm["tp"] + cm["fn"], cm["tp"] + cm["fp"]
    chance = actual * predicted + (n - actual) * (n - predicted)
    if chance == n * n:
        raise ValueError("Cohen's kappa is undefined")
    return ((cm["tp"] + cm["tn"]) * n - chance) / (n * n - chance)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    denominator = sensitivity + specificity - 1
    if abs(denominator) < 1e-12:
        return float("nan")
    return min(1.0, max(0.0, (observed_rate + specificity - 1) / denominator))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy.stats import bootstrap

    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.ndim != 1 or a.shape != b.shape or not a.size:
        raise ValueError("paired samples must be non-empty vectors of equal length")
    differences = a - b
    if np.all(differences == differences[0]):
        value = float(differences[0])
        return value, value, value
    result = bootstrap(
        (a, b), lambda x, y, axis: np.mean(x - y, axis=axis),
        paired=True, method="percentile", n_resamples=n_resamples,
        confidence_level=confidence, rng=np.random.default_rng(rng),
    )
    return float(differences.mean()), float(result.confidence_interval.low), float(result.confidence_interval.high)


def _validate_pass_args(n: int, c: int, k: int) -> None:
    if (not all(isinstance(v, Integral) and not isinstance(v, bool) for v in (n, c, k))
            or not 0 <= c <= n or not 1 <= k <= n):
        raise ValueError("expected integers with 0 <= c <= n and 1 <= k <= n")


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    _validate_pass_args(n, c, k)
    total = comb(n, k)
    return (total - comb(n - c, k)) / total


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    _validate_pass_args(n, c, k)
    return comb(c, k) / comb(n, k)
