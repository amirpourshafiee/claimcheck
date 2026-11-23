import pytest

from claimcheck.compare import flagged_f1, paired_f1_difference


def rows(spec):
    """spec: list of (claim_id, answer_id, gold_flagged, pred_flagged)."""
    return {
        cid: {
            "claim_id": cid,
            "answer_id": ans,
            "gold": "CONTRADICTED" if g else "SUPPORTED",
            "gold_flagged": str(g),
            "pred_flagged": str(p),
        }
        for cid, ans, g, p in spec
    }


def test_flagged_f1_counts_only_the_flagged_class():
    r = rows([("a", "q1", True, True), ("b", "q1", True, False), ("c", "q1", False, True)])
    assert flagged_f1(["a", "b", "c"], r) == pytest.approx(0.5)  # tp=1 fp=1 fn=1


def test_flagged_f1_is_zero_when_nothing_is_flagged_anywhere():
    r = rows([("a", "q1", False, False)])
    assert flagged_f1(["a"], r) == 0.0


def test_paired_difference_is_positive_when_a_is_better_on_every_answer():
    ids = [f"c{i}" for i in range(12)]
    spec_a = [(c, f"q{i % 4}", True, True) for i, c in enumerate(ids)]
    spec_b = [(c, f"q{i % 4}", True, i % 2 == 0) for i, c in enumerate(ids)]
    r = paired_f1_difference(rows(spec_a), rows(spec_b), ids, n_resamples=300, seed=1)
    assert r["diff"] > 0 and r["ci"][0] >= 0 and r["answers"] == 4


def test_identical_judges_have_zero_difference():
    ids = ["a", "b", "c", "d"]
    spec = [(c, f"q{i % 2}", i % 2 == 0, i % 2 == 0) for i, c in enumerate(ids)]
    r = paired_f1_difference(rows(spec), rows(spec), ids, n_resamples=100)
    assert r["diff"] == 0 and r["ci"] == (0.0, 0.0)


def test_mismatched_gold_labels_are_rejected():
    a = rows([("a", "q1", True, True)])
    b = rows([("a", "q1", False, True)])
    with pytest.raises(ValueError, match="gold"):
        paired_f1_difference(a, b, ["a"], n_resamples=10)
