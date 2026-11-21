import json

import pytest

from claimcheck.extract import ExtractionError, extract_claims, parse_claims
from claimcheck.llm import ScriptedClient

GOOD = json.dumps(
    [
        {"text": "The Tower is 330 metres tall.", "citation": "S1"},
        {"text": "It opened in 1889.", "citation": "[s2]"},
        {"text": "It has no marker.", "citation": None},
    ]
)


def test_parse_assigns_sequential_ids_and_normalizes_citations():
    claims = parse_claims(GOOD, "q07")
    assert [c.claim_id for c in claims] == ["q07-c01", "q07-c02", "q07-c03"]
    assert [c.citation_id for c in claims] == ["S1", "S2", None]


def test_parse_tolerates_markdown_code_fences():
    fenced = f"```json\n{GOOD}\n```"
    assert len(parse_claims(fenced, "q01")) == 3


@pytest.mark.parametrize(
    "bad",
    [
        "not json at all",
        "[]",  # empty list is an error, not "no claims"
        '{"text": "x"}',  # object, not array
        '[{"claim": "wrong key"}]',
        '[{"text": "   "}]',
        '[{"text": "ok", "citation": "see above"}]',
    ],
)
def test_parse_raises_on_malformed_replies(bad):
    with pytest.raises(ExtractionError):
        parse_claims(bad, "q01")


def test_extract_claims_sends_answer_to_the_model_and_parses_reply():
    client = ScriptedClient([GOOD])
    claims = extract_claims("q01", "  The Tower is 330 metres tall. [S1]  ", client)
    assert len(claims) == 3
    ((system, user),) = client.calls
    assert "atomic claims" in system
    assert user == "Answer:\nThe Tower is 330 metres tall. [S1]"


def test_extract_claims_propagates_bad_reply_instead_of_hiding_it():
    with pytest.raises(ExtractionError):
        extract_claims("q01", "answer", ScriptedClient(["Sure! Here are the claims: ..."]))
