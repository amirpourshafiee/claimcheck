import json

import pytest

from claimcheck.schema import Claim, Label, Report, Verdict


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("SUPPORTED", Label.SUPPORTED),
        ("supported", Label.SUPPORTED),
        ("  Not Mentioned ", Label.NOT_MENTIONED),
        ("citation-missing", Label.CITATION_MISSING),
        ("contradicted", Label.CONTRADICTED),
    ],
)
def test_label_parse_tolerates_case_and_separators(raw, expected):
    assert Label.parse(raw) is expected


def test_label_parse_rejects_unknown_value():
    with pytest.raises(ValueError):
        Label.parse("probably true")


def test_only_supported_is_not_flagged():
    flagged = {label for label in Label if label.is_flagged}
    assert flagged == {Label.CONTRADICTED, Label.NOT_MENTIONED, Label.CITATION_MISSING}


def test_claim_rejects_empty_text():
    with pytest.raises(ValueError):
        Claim(claim_id="q01-c01", text="   ")


def test_verdict_roundtrips_through_json():
    v = Verdict("q01-c01", Label.CONTRADICTED, rationale="date differs", judge="mock")
    restored = Verdict.from_dict(json.loads(json.dumps(v.to_dict())))
    assert restored == v


def test_report_summary_includes_zero_counts():
    report = Report(
        answer_id="q01",
        verdicts=[
            Verdict("a", Label.SUPPORTED),
            Verdict("b", Label.NOT_MENTIONED),
            Verdict("c", Label.NOT_MENTIONED),
        ],
    )
    assert report.summary() == {
        "SUPPORTED": 1,
        "CONTRADICTED": 0,
        "NOT_MENTIONED": 2,
        "CITATION_MISSING": 0,
    }
    assert [v.claim_id for v in report.flagged()] == ["b", "c"]
