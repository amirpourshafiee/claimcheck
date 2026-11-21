"""End-to-end pipeline: answer -> claims -> matched sources -> verdicts -> report."""

from __future__ import annotations

from collections.abc import Sequence

from claimcheck.extract import extract_claims
from claimcheck.judge import Judge
from claimcheck.llm import LLMClient
from claimcheck.match import MatchStatus, match_claim, missing_verdict
from claimcheck.schema import Claim, Report


def check_claims(
    answer_id: str, claims: Sequence[Claim], sources: dict[str, str], judge: Judge
) -> Report:
    """Stages 2 and 3 on claims that already exist (for example the hand-verified gold claims).

    Verdicts keep the order of the claims. Errors from the judge propagate on purpose: a budget
    stop (CallBudgetExceeded) or a malformed reply must stop the run, not be swallowed.
    """
    report = Report(answer_id=answer_id, claims=list(claims))
    for claim in claims:
        m = match_claim(claim, sources)
        if m.status is MatchStatus.UNCITED:
            report.uncited.append(claim.claim_id)
        elif m.status is MatchStatus.MISSING:
            report.verdicts.append(missing_verdict(m))
        else:
            assert m.source_text is not None
            report.verdicts.append(judge.judge(claim, m.source_text))
    return report


def run_pipeline(
    answer_id: str,
    answer_text: str,
    sources: dict[str, str],
    extract_client: LLMClient,
    judge: Judge,
) -> Report:
    """Full pipeline including stage 1 (claim extraction by an LLM)."""
    claims = extract_claims(answer_id, answer_text, extract_client)
    return check_claims(answer_id, claims, sources, judge)
