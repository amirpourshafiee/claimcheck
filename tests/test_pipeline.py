import json

import pytest

from claimcheck.llm import CallBudgetExceeded, ScriptedClient
from claimcheck.pipeline import check_claims, run_pipeline
from claimcheck.report import to_json, to_markdown
from claimcheck.schema import Claim, Label, Report, Verdict

SOURCES = {"S1": "source one text", "S2": "source two text"}


class StubJudge:
    name = "stub"

    def __init__(self, label=Label.SUPPORTED):
        self.label = label
        self.seen: list[tuple[str, str]] = []

    def judge(self, claim, source_text):
        self.seen.append((claim.claim_id, source_text))
        return Verdict(claim.claim_id, self.label, "stub", judge=self.name)


def test_check_claims_routes_each_claim_by_match_status_in_order():
    claims = [
        Claim("c1", "matched", "S2"),
        Claim("c2", "fake source", "S9"),
        Claim("c3", "no citation", None),
        Claim("c4", "matched too", "S1"),
    ]
    judge = StubJudge()
    report = check_claims("q01", claims, SOURCES, judge)
    assert [v.claim_id for v in report.verdicts] == ["c1", "c2", "c4"]  # claim order kept
    assert report.verdicts[1].label is Label.CITATION_MISSING
    assert report.uncited == ["c3"]
    # The judge is called only for matched claims, and sees the cited source's text.
    assert judge.seen == [("c1", "source two text"), ("c4", "source one text")]


def test_budget_errors_stop_the_run_instead_of_being_swallowed():
    class Exhausted:
        name = "x"

        def judge(self, claim, source_text):
            raise CallBudgetExceeded("cap reached")

    with pytest.raises(CallBudgetExceeded):
        check_claims("q01", [Claim("c1", "t", "S1")], SOURCES, Exhausted())


def test_run_pipeline_extracts_then_checks():
    extract_reply = json.dumps(
        [{"text": "Claim A.", "citation": "S1"}, {"text": "Claim B.", "citation": "S3"}]
    )
    report = run_pipeline(
        "q05",
        "answer text",
        SOURCES,
        ScriptedClient([extract_reply]),
        StubJudge(Label.CONTRADICTED),
    )
    assert [c.claim_id for c in report.claims] == ["q05-c01", "q05-c02"]
    assert [v.label for v in report.verdicts] == [Label.CONTRADICTED, Label.CITATION_MISSING]


def _sample_report() -> Report:
    claims = [
        Claim("c1", "It has a | pipe", "S1"),
        Claim("c2", "Fine claim", "S1"),
        Claim("c3", "Uncited claim", None),
    ]
    return Report(
        "q01",
        claims,
        [
            Verdict("c1", Label.CONTRADICTED, "source says\n35"),
            Verdict("c2", Label.SUPPORTED),
        ],
        uncited=["c3"],
    )


def test_markdown_lists_flagged_before_supported_and_escapes_pipes():
    md = to_markdown(_sample_report())
    assert md.index("## Flagged claims") < md.index("## Supported claims")
    assert "It has a \\| pipe" in md  # a raw pipe would break the table
    assert "source says 35" in md  # newlines collapsed
    assert "## Not evaluated (no citation)" in md and "Uncited claim" in md
    assert "1 of 2 checked claims were flagged." in md


def test_json_report_is_valid_and_includes_summary_and_uncited():
    data = json.loads(to_json(_sample_report()))
    assert data["summary"]["CONTRADICTED"] == 1
    assert data["uncited"] == ["c3"]
    assert data["verdicts"][0]["label"] == "CONTRADICTED"
