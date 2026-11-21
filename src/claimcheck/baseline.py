"""A free, non-LLM baseline judge: word overlap plus number matching.

Why it exists: an F1 of 0.85 means little without a floor to compare against. If this crude
heuristic scores close to the LLM judge, the LLM adds little on this dataset, and the report
should say so honestly.

Rule: SUPPORTED when enough of the claim's content words appear in the source AND every number
in the claim appears in the source. Otherwise NOT_MENTIONED. It never predicts CONTRADICTED:
telling "different" from "absent" needs meaning, not word overlap. Its threshold must be tuned
on the dev split only, never on the test split.
"""

from __future__ import annotations

import re

from claimcheck.schema import Claim, Label, Verdict

STOPWORDS = frozenset(
    "a an and are as at be been but by can could did do does for from had has have he her his "
    "how if in into is it its of on or she so than that the their them then there these they "
    "this those to was were what when where which while who why will with would".split()
)
_WORD = re.compile(r"[a-z0-9]+")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def content_tokens(text: str) -> set[str]:
    """Lowercase words without stopwords or single characters."""
    return {w for w in _WORD.findall(text.lower()) if w not in STOPWORDS and len(w) > 1}


def numbers(text: str) -> set[str]:
    """Numbers as strings, with thousands commas removed ("1,901" becomes "1901")."""
    return {m.group(0).replace(",", "").rstrip(".") for m in _NUMBER.finditer(text)}


class LexicalBaseline:
    def __init__(self, threshold: float = 0.7, name: str = "baseline-lexical"):
        self.threshold = threshold
        self.name = name

    def judge(self, claim: Claim, source_text: str) -> Verdict:
        claim_words = content_tokens(claim.text)
        if not claim_words:
            return Verdict(
                claim.claim_id, Label.NOT_MENTIONED, "claim has no content words", judge=self.name
            )
        overlap = len(claim_words & content_tokens(source_text)) / len(claim_words)
        missing_numbers = numbers(claim.text) - numbers(source_text)
        if overlap >= self.threshold and not missing_numbers:
            label = Label.SUPPORTED
        else:
            label = Label.NOT_MENTIONED
        why = f"word overlap {overlap:.2f} (threshold {self.threshold})"
        if missing_numbers:
            why += f"; numbers not in source: {sorted(missing_numbers)}"
        return Verdict(claim.claim_id, label, why, judge=self.name)
