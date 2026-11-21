import pytest

from claimcheck.match import (
    MatchStatus,
    match_claim,
    missing_verdict,
    normalize_citation_id,
)
from claimcheck.schema import Claim, Label

SOURCES = {"S1": "text one", "S2": "text two"}


@pytest.mark.parametrize(
    "raw, expected",
    [("S1", "S1"), ("[s2]", "S2"), ("  S3 ", "S3"), ("[ S4 ]", "S4"), ("", None), (None, None)],
)
def test_normalize_citation_id(raw, expected):
    assert normalize_citation_id(raw) == expected


@pytest.mark.parametrize("bad", ["see above", "S", "1", "S1, S2"])
def test_normalize_rejects_non_ids(bad):
    with pytest.raises(ValueError):
        normalize_citation_id(bad)


def test_matched_claim_carries_its_source_text():
    m = match_claim(Claim("c1", "fact", "S2"), SOURCES)
    assert (m.status, m.source_text) == (MatchStatus.MATCHED, "text two")


def test_bracketed_lowercase_citation_still_matches():
    assert match_claim(Claim("c1", "fact", "[s1]"), SOURCES).status is MatchStatus.MATCHED


def test_unknown_source_id_is_missing_and_needs_no_judge():
    m = match_claim(Claim("c1", "fact", "S3"), SOURCES)
    assert m.status is MatchStatus.MISSING and m.source_text is None
    v = missing_verdict(m)
    assert v.label is Label.CITATION_MISSING and v.judge == "match"


def test_claim_without_citation_is_uncited():
    assert match_claim(Claim("c1", "fact", None), SOURCES).status is MatchStatus.UNCITED


def test_missing_verdict_refuses_other_statuses():
    with pytest.raises(ValueError):
        missing_verdict(match_claim(Claim("c1", "fact", "S1"), SOURCES))
