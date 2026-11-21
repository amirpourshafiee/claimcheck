"""Stage 2: match each claim to the source it cites. Deterministic, no LLM.

A claim cites exactly one source id. Three outcomes:
- MATCHED: the id is in the provided sources, so the judge will compare claim and source text.
- MISSING: the id is not among the provided sources. The verdict is CITATION_MISSING and the judge
  is never called, which also saves money.
- UNCITED: the claim has no citation. Out of scope for v1; reported as not evaluated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from claimcheck.schema import Claim, Label, Verdict


class MatchStatus(str, Enum):
    MATCHED = "MATCHED"
    MISSING = "MISSING"
    UNCITED = "UNCITED"


@dataclass(frozen=True)
class Match:
    claim: Claim
    status: MatchStatus
    source_text: str | None = None


def normalize_citation_id(raw: str | None) -> str | None:
    """Turn "[s2]", " S2 ", or "S2" into "S2". Empty or None becomes None.

    Raises ValueError for text that does not look like a source id (for example "see above"),
    so a malformed model reply fails loudly instead of becoming a bogus id.
    """
    if raw is None or not raw.strip():
        return None
    m = re.fullmatch(r"\s*\[?\s*([A-Za-z]+\d+)\s*\]?\s*", raw)
    if not m:
        raise ValueError(f"not a valid citation id: {raw!r}")
    return m.group(1).upper()


def match_claim(claim: Claim, sources: dict[str, str]) -> Match:
    """Look up the cited source for one claim. `sources` maps source id to excerpt text."""
    cid = normalize_citation_id(claim.citation_id)
    if cid is None:
        return Match(claim, MatchStatus.UNCITED)
    if cid not in sources:
        return Match(claim, MatchStatus.MISSING)
    return Match(claim, MatchStatus.MATCHED, source_text=sources[cid])


def missing_verdict(match: Match) -> Verdict:
    """The verdict for a MISSING match. Never needs a judge."""
    if match.status is not MatchStatus.MISSING:
        raise ValueError("missing_verdict requires a MISSING match")
    return Verdict(
        claim_id=match.claim.claim_id,
        label=Label.CITATION_MISSING,
        rationale=f"cited source {match.claim.citation_id!r} was not provided",
        judge="match",
    )
