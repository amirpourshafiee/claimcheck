import pytest

from claimcheck.metrics import (
    bootstrap_ci,
    cohen_kappa,
    confusion_matrix,
    flagged_prf,
)
from claimcheck.schema import Label

S, C, N, M = (
    Label.SUPPORTED,
    Label.CONTRADICTED,
    Label.NOT_MENTIONED,
    Label.CITATION_MISSING,
)


def test_flagged_prf_matches_hand_computation():
    # Flagged = anything but SUPPORTED. By hand: tp=3 (idx 1,3,5), fp=1 (idx 4),
    # fn=1 (idx 2), tn=1 (idx 0). Precision 3/4, recall 3/4, F1 3/4.
    y_true = [S, C, N, M, S, N]
    y_pred = [S, N, S, M, C, N]
    r = flagged_prf(y_true, y_pred)
    assert (r.tp, r.fp, r.fn, r.tn) == (3, 1, 1, 1)
    assert (r.precision, r.recall, r.f1) == (0.75, 0.75, 0.75)


def test_wrong_flag_type_still_counts_as_a_correct_flag():
    # True CONTRADICTED predicted NOT_MENTIONED: both are flagged, so it is a true positive for
    # the headline metric. The confusion matrix is where the type confusion shows up.
    r = flagged_prf([C], [N])
    assert (r.tp, r.fp, r.fn) == (1, 0, 0)


def test_zero_denominators_give_zero_not_a_crash():
    r = flagged_prf([S, S], [S, S])  # nothing to find, nothing flagged
    assert (r.precision, r.recall, r.f1) == (0.0, 0.0, 0.0)
    assert r.tn == 2  # the counts reveal it was a vacuous case


def test_length_mismatch_and_empty_input_are_rejected():
    with pytest.raises(ValueError):
        flagged_prf([S], [S, S])
    with pytest.raises(ValueError):
        flagged_prf([], [])


def test_confusion_matrix_counts_and_includes_every_label():
    m = confusion_matrix([S, C, C, N], [S, C, N, N])
    assert m["CONTRADICTED"]["CONTRADICTED"] == 1
    assert m["CONTRADICTED"]["NOT_MENTIONED"] == 1
    assert m["CITATION_MISSING"] == {label.value: 0 for label in Label}  # all-zero row present
    assert sum(sum(row.values()) for row in m.values()) == 4


def test_kappa_hand_computed_example():
    # po = 3/4. a: 50% S, 50% N. b: 25% S, 75% N. pe = .5*.25 + .5*.75 = .5.
    # kappa = (.75 - .5) / (1 - .5) = .5
    assert cohen_kappa([S, S, N, N], [S, N, N, N]) == pytest.approx(0.5)


def test_kappa_perfect_chance_and_degenerate():
    assert cohen_kappa([S, N, C], [S, N, C]) == 1.0
    assert cohen_kappa([S, S, N, N], [S, N, S, N]) == pytest.approx(0.0)  # chance level
    assert cohen_kappa([S, S], [S, S]) == 1.0  # pe == 1 case handled, no division by zero
    assert cohen_kappa([S, S], [N, N]) == 0.0


def test_bootstrap_is_reproducible_and_collapses_for_perfect_predictions():
    y = [N, S] * 10
    f1 = lambda t, p: flagged_prf(t, p).f1  # noqa: E731
    lo, hi = bootstrap_ci(y, y, f1, seed=7)
    assert (lo, hi) == (1.0, 1.0)  # perfect predictions: no uncertainty at 20 items
    noisy = [N, S, N, N, S, S, N, S, N, S, N, N, S, N, S, S, N, S, N, S]
    assert bootstrap_ci(y, noisy, f1, seed=3) == bootstrap_ci(y, noisy, f1, seed=3)


def test_cluster_bootstrap_is_wider_than_naive_when_claims_cluster():
    # 10 answers of 5 claims each. Within an answer every claim is right or every claim is wrong,
    # so claims are far from independent. Resampling whole answers must give a wider interval.
    true, pred, groups = [], [], []
    for g in range(10):
        for _ in range(5):
            true.append(S)
            pred.append(S if g < 5 else N)
            groups.append(f"q{g}")
    accuracy = lambda t, p: sum(a == b for a, b in zip(t, p, strict=True)) / len(t)  # noqa: E731
    naive = bootstrap_ci(true, pred, accuracy, seed=1)
    clustered = bootstrap_ci(true, pred, accuracy, groups=groups, seed=1)
    assert clustered[1] - clustered[0] > naive[1] - naive[0]
