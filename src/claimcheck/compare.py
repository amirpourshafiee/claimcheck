"""Paired comparison of two judges on the same claims, from their predictions files.

Two intervals that overlap do not prove two judges are alike, because both are computed on the
same claims. The paired test resamples whole answers once and scores BOTH judges on every
resample, so it measures the difference directly.

    python -m claimcheck.compare results/a_test_predictions.csv results/b_test_predictions.csv
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path


def load_predictions(path: Path) -> dict[str, dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return {r["claim_id"]: r for r in csv.DictReader(f)}


def flagged_f1(ids: list[str], rows: dict[str, dict[str, str]]) -> float:
    tp = fp = fn = 0
    for i in ids:
        gold = rows[i]["gold_flagged"] == "True"
        pred = rows[i]["pred_flagged"] == "True"
        tp += gold and pred
        fp += (not gold) and pred
        fn += gold and not pred
    denom = 2 * tp + fp + fn
    return 2 * tp / denom if denom else 0.0


def paired_f1_difference(
    a: dict[str, dict[str, str]],
    b: dict[str, dict[str, str]],
    ids: list[str],
    n_resamples: int = 5000,
    seed: int = 0,
    confidence: float = 0.95,
) -> dict:
    """F1(a) minus F1(b) over `ids`, with a percentile interval from resampling answers."""
    if not ids:
        raise ValueError("no claims to compare")
    for i in ids:
        if a[i]["gold"] != b[i]["gold"]:
            raise ValueError(f"{i}: the two files disagree on the gold label")
    by_answer: dict[str, list[str]] = defaultdict(list)
    for i in ids:
        by_answer[a[i]["answer_id"]].append(i)
    answers = sorted(by_answer)
    rng = random.Random(seed)
    diffs = []
    for _ in range(n_resamples):
        sample = [i for ans in (rng.choice(answers) for _ in answers) for i in by_answer[ans]]
        diffs.append(flagged_f1(sample, a) - flagged_f1(sample, b))
    diffs.sort()
    tail = (1 - confidence) / 2
    lo = diffs[int(n_resamples * tail)]
    hi = diffs[int(n_resamples * (1 - tail)) - 1]
    return {
        "n": len(ids),
        "answers": len(answers),
        "f1_a": flagged_f1(ids, a),
        "f1_b": flagged_f1(ids, b),
        "diff": flagged_f1(ids, a) - flagged_f1(ids, b),
        "ci": (lo, hi),
        "p_diff_not_positive": sum(d <= 0 for d in diffs) / n_resamples,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("a", type=Path, help="predictions CSV of the judge expected to be better")
    ap.add_argument("b", type=Path, help="predictions CSV of the comparison judge")
    ap.add_argument("--resamples", type=int, default=5000)
    args = ap.parse_args(argv)
    a, b = load_predictions(args.a), load_predictions(args.b)
    if set(a) != set(b):
        print("the two files cover different claims", file=sys.stderr)
        return 2
    slices = {
        "organic": [i for i in a if a[i]["origin"] == "organic"],
        "judge_only (all)": [i for i in a if a[i]["gold"] != "CITATION_MISSING"],
    }
    for name, ids in slices.items():
        r = paired_f1_difference(a, b, ids, args.resamples)
        print(
            f"{name}: n={r['n']} answers={r['answers']} F1 {r['f1_a']:.3f} vs {r['f1_b']:.3f}, "
            f"diff {r['diff']:+.3f}, 95% CI [{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}], "
            f"share of resamples with diff <= 0: {r['p_diff_not_positive']:.3f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
