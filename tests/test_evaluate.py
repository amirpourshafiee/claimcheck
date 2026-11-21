import pytest

from claimcheck.dataset import Example
from claimcheck.evaluate import check_run_allowed, evaluate, run_judge, to_markdown
from claimcheck.schema import Claim, Label, Verdict

S, C, N, M = (
    Label.SUPPORTED,
    Label.CONTRADICTED,
    Label.NOT_MENTIONED,
    Label.CITATION_MISSING,
)


def ex(cid, gold, origin="organic", answer="q01", citation="S1"):
    return Example(Claim(cid, "text", citation), answer, "dev", origin, "", gold)


def verdicts(**labels):
    return {cid: Verdict(cid, label) for cid, label in labels.items()}


def test_judge_only_view_excludes_missing_citation_rows():
    # gold [S, N, M, C], predicted [S, S, M, C].
    examples = [ex("a", S), ex("b", N), ex("c", M), ex("d", C)]
    res = evaluate(examples, verdicts(a=S, b=S, c=M, d=C), n_resamples=50)
    by_view = {v: {s["slice"]: s for s in d["slices"]} for v, d in res["views"].items()}
    e2e = by_view["end_to_end"]["all"]
    # flagged gold = b, c, d. Caught c and d. Missed b. Precision 2/2, recall 2/3, F1 0.8.
    assert (e2e["tp"], e2e["fp"], e2e["fn"]) == (2, 0, 1)
    assert e2e["f1"] == pytest.approx(0.8)
    judged = by_view["judge_only"]["all"]
    # Without row c the judge is scored on 3 claims: caught d, missed b. Recall 1/2, F1 2/3.
    assert judged["n"] == 3 and judged["recall"] == pytest.approx(0.5)
    assert judged["f1"] == pytest.approx(2 / 3)


def test_matcher_check_reports_catches_and_false_alarms():
    examples = [ex("a", M), ex("b", M), ex("c", S)]
    res = evaluate(examples, verdicts(a=M, b=S, c=M), n_resamples=50)
    assert res["matcher_check"] == {"gold_citation_missing": 2, "caught": 1, "false_alarms": 1}


def test_slices_are_reported_separately_by_origin():
    examples = [
        ex("o1", S),
        ex("o2", N),
        ex("p1", C, origin="planted"),
        ex("p2", N, origin="planted"),
    ]
    res = evaluate(examples, verdicts(o1=S, o2=S, p1=C, p2=N), n_resamples=50)
    slices = {s["slice"]: s for s in res["views"]["end_to_end"]["slices"]}
    assert slices["organic"]["recall"] == 0.0  # the judge missed the only organic flag
    assert slices["planted"]["recall"] == 1.0  # and caught every planted one
    assert slices["all"]["n"] == 4  # pooled hides that difference, hence the slices


def test_evaluate_rejects_unlabeled_examples():
    unlabeled = Example(Claim("a", "t", "S1"), "q01", "dev", "organic", "", None)
    with pytest.raises(ValueError):
        evaluate([unlabeled], verdicts(a=S))


def test_run_judge_calls_judge_only_for_matched_claims():
    class Stub:
        name = "stub"

        def __init__(self):
            self.seen = []

        def judge(self, claim, source_text):
            self.seen.append(claim.claim_id)
            return Verdict(claim.claim_id, S)

    examples = [ex("a", S), ex("b", M, citation="S9")]
    stub = Stub()
    out = run_judge(examples, {"q01": {"S1": "text"}}, stub)
    assert stub.seen == ["a"]
    assert out["b"].label is M


def test_markdown_contains_both_views_and_ci_text():
    res = evaluate([ex("a", N), ex("b", S)], verdicts(a=N, b=S), n_resamples=50)
    md = to_markdown(res, "demo")
    assert "## end_to_end" in md and "## judge_only" in md and "F1 (95% CI)" in md
    assert "Citation matcher:" in md


def test_test_split_is_blocked_without_final_flag():
    assert "reserved" in check_run_allowed("test", False, "baseline", False)
    assert "reserved" in check_run_allowed("all", False, "baseline", False)
    assert check_run_allowed("test", True, "baseline", False) is None
    assert check_run_allowed("dev", False, "baseline", False) is None


def test_paid_runs_require_explicit_confirmation():
    assert "spends money" in check_run_allowed("dev", False, "llm", False)
    assert check_run_allowed("dev", False, "llm", True) is None


def test_ci_is_withheld_when_too_few_answers_to_resample():
    # All items come from one answer: a cluster bootstrap would return a zero-width interval,
    # which would wrongly look like certainty. It must be reported as unavailable.
    one_answer = [ex("a", N), ex("b", S), ex("c", C)]
    res = evaluate(one_answer, verdicts(a=N, b=S, c=C), n_resamples=50)
    assert res["views"]["end_to_end"]["slices"][0]["f1_ci95"] is None
    many = [ex(f"x{i}", N, answer=f"q{i}") for i in range(6)]
    res = evaluate(many, verdicts(**{f"x{i}": N for i in range(6)}), n_resamples=50)
    assert res["views"]["end_to_end"]["slices"][0]["f1_ci95"] is not None


def test_run_judge_survives_an_unparseable_reply_and_counts_it():
    from claimcheck.judge import JudgeError

    class Flaky:
        name = "flaky"

        def judge(self, claim, source_text):
            if claim.claim_id == "bad":
                raise JudgeError("reply is not valid JSON")
            return Verdict(claim.claim_id, C)

    examples = [ex("good", C), ex("bad", C)]
    out = run_judge(examples, {"q01": {"S1": "text"}}, Flaky())
    assert out["good"].label is C
    # Scored as not flagged, so it is a miss against a flagged gold label, never a free hit.
    assert out["bad"].label is S and out["bad"].rationale.startswith("[judge error]")
    results = evaluate(examples, out)
    assert results["judge_errors"] == ["bad"]
    assert results["views"]["end_to_end"]["slices"][0]["fn"] == 1
    assert "Judge errors" in to_markdown(results, "t")
