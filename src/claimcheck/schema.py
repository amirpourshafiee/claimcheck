"""Core data types shared by every pipeline stage.

Kept dependency-free (standard library only) so the schema is easy to read and test.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class Label(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    NOT_MENTIONED = "NOT_MENTIONED"
    CITATION_MISSING = "CITATION_MISSING"

    @classmethod
    def parse(cls, value: str) -> Label:
        """Parse a label string, tolerating case, spaces, and hyphens.

        Raises ValueError for anything else, so a malformed LLM reply fails loudly
        instead of silently becoming a wrong label.
        """
        key = value.strip().upper().replace(" ", "_").replace("-", "_")
        try:
            return cls[key]
        except KeyError:
            raise ValueError(f"Unknown label: {value!r}") from None

    @property
    def is_flagged(self) -> bool:
        """True for every label except SUPPORTED. This is the positive class for metrics."""
        return self is not Label.SUPPORTED


@dataclass(frozen=True)
class Claim:
    """One atomic, self-contained factual statement from an answer.

    citation_id is the single source the claim cites (for example "S1"). The dataset allows
    exactly one citation per claim to keep labeling unambiguous. See the datasheet.
    """

    claim_id: str
    text: str
    citation_id: str | None = None

    def __post_init__(self) -> None:
        if not self.claim_id.strip():
            raise ValueError("claim_id must be non-empty")
        if not self.text.strip():
            raise ValueError("claim text must be non-empty")


@dataclass(frozen=True)
class Verdict:
    """A judge's decision about one claim."""

    claim_id: str
    label: Label
    rationale: str = ""
    evidence_quote: str = ""
    judge: str = ""  # which judge produced this, for example "baseline-lexical"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["label"] = self.label.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Verdict:
        return cls(
            claim_id=d["claim_id"],
            label=Label.parse(d["label"]),
            rationale=d.get("rationale", ""),
            evidence_quote=d.get("evidence_quote", ""),
            judge=d.get("judge", ""),
        )


@dataclass
class Report:
    """The flagged report for one answer."""

    answer_id: str
    claims: list[Claim] = field(default_factory=list)
    verdicts: list[Verdict] = field(default_factory=list)
    # Claim ids with no citation. They are out of scope for v1 and reported as not evaluated.
    uncited: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, int]:
        """Count of verdicts per label, always including every label (zeros included)."""
        counts = {label.value: 0 for label in Label}
        for v in self.verdicts:
            counts[v.label.value] += 1
        return counts

    def flagged(self) -> list[Verdict]:
        return [v for v in self.verdicts if v.label.is_flagged]

    def to_dict(self) -> dict:
        return {
            "answer_id": self.answer_id,
            "summary": self.summary(),
            "uncited": list(self.uncited),
            "claims": [asdict(c) for c in self.claims],
            "verdicts": [v.to_dict() for v in self.verdicts],
        }
