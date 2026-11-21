"""Evaluation metrics, written by hand so every number is auditable.

Headline metric: precision, recall, and F1 for the FLAGGED class (any label except SUPPORTED).
Also provided: the 4-class confusion matrix, Cohen's kappa for agreement between two labelers,
and a bootstrap confidence interval. With about 90 claims, point estimates alone overstate how
much we know, so always report the interval next to the number.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from claimcheck.schema import Label


@dataclass(frozen=True)
class PRF:
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int
    tn: int


def _check_same_length(a: Sequence, b: Sequence) -> None:
    if len(a) != len(b):
        raise ValueError(f"length mismatch: {len(a)} vs {len(b)}")
    if not a:
        raise ValueError("need at least one item")


def flagged_prf(y_true: Sequence[Label], y_pred: Sequence[Label]) -> PRF:
    """Precision, recall, F1 where the positive class is 'flagged' (not SUPPORTED).

    Convention: a metric whose denominator is zero is reported as 0.0. The raw counts are
    returned too, so a 0.0 caused by "nothing to find" is visible and not mistaken for failure.
    """
    _check_same_length(y_true, y_pred)
    tp = sum(t.is_flagged and p.is_flagged for t, p in zip(y_true, y_pred, strict=True))
    fp = sum((not t.is_flagged) and p.is_flagged for t, p in zip(y_true, y_pred, strict=True))
    fn = sum(t.is_flagged and (not p.is_flagged) for t, p in zip(y_true, y_pred, strict=True))
    tn = len(y_true) - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return PRF(precision, recall, f1, tp, fp, fn, tn)


def confusion_matrix(y_true: Sequence[Label], y_pred: Sequence[Label]) -> dict[str, dict[str, int]]:
    """Rows are the true label, columns the predicted label. Every label appears in both axes."""
    _check_same_length(y_true, y_pred)
    matrix = {t.value: {p.value: 0 for p in Label} for t in Label}
    for t, p in zip(y_true, y_pred, strict=True):
        matrix[t.value][p.value] += 1
    return matrix


def cohen_kappa(a: Sequence[Label], b: Sequence[Label]) -> float:
    """Cohen's kappa: agreement beyond what chance alone would produce.

    kappa = (po - pe) / (1 - pe), where po is observed agreement and pe is the agreement expected
    if both raters picked labels independently with their own label frequencies.
    1.0 is perfect, 0.0 is chance level, negative is worse than chance.
    Degenerate case (pe == 1, both raters used one identical label throughout): returns 1.0 if
    they agree everywhere, otherwise 0.0.
    """
    _check_same_length(a, b)
    n = len(a)
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[label] / n) * (cb[label] / n) for label in Label)
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def bootstrap_ci(
    y_true: Sequence[Label],
    y_pred: Sequence[Label],
    stat: Callable[[list[Label], list[Label]], float],
    groups: Sequence[str] | None = None,
    n_resamples: int = 2000,
    seed: int = 0,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval for `stat(y_true, y_pred)`.

    Pass `groups` (for example the answer id of every claim) to resample whole groups. Claims
    from the same answer are not independent, so resampling single claims would give an interval
    that is too narrow. Seeded, so the same inputs always give the same interval.
    """
    _check_same_length(y_true, y_pred)
    if groups is None:
        groups = [str(i) for i in range(len(y_true))]
    _check_same_length(y_true, groups)
    members: dict[str, list[int]] = {}
    for i, g in enumerate(groups):
        members.setdefault(g, []).append(i)
    keys = list(members)
    rng = random.Random(seed)
    values = []
    for _ in range(n_resamples):
        idx = [i for g in rng.choices(keys, k=len(keys)) for i in members[g]]
        values.append(stat([y_true[i] for i in idx], [y_pred[i] for i in idx]))
    values.sort()
    tail = (1 - confidence) / 2
    lo = values[int(tail * len(values))]
    hi = values[min(len(values) - 1, int((1 - tail) * len(values)))]
    return lo, hi
