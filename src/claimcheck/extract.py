"""Stage 1: split an AI answer into atomic claims using an LLM.

The model reply is untrusted text. `parse_claims` validates it strictly and raises
`ExtractionError` on anything malformed. There is no silent fallback, because a silently dropped
claim would hide exactly the errors this tool exists to find.
"""

from __future__ import annotations

import json
import re

from claimcheck.llm import LLMClient
from claimcheck.match import normalize_citation_id
from claimcheck.schema import Claim

SYSTEM_PROMPT = """You split an answer into atomic claims for fact checking.

Rules:
1. One claim is one checkable fact. If a sentence holds two facts, output two claims.
2. Each claim must stand alone. Replace pronouns such as "it" or "they" with the specific name.
3. Keep the meaning exactly. Do not add facts, drop qualifiers such as "about" or "may", or
   correct anything.
4. Each claim keeps the citation marker of the sentence it came from, as a source id such as
   "S1" (no brackets). Use null if the sentence has no marker.
5. Do not judge whether any claim is true.

Reply with ONLY a JSON array, in the order the claims appear, like:
[{"text": "The tower is 330 metres tall.", "citation": "S1"}]
"""


class ExtractionError(ValueError):
    """The model reply could not be turned into a valid claim list."""


def build_user_prompt(answer_text: str) -> str:
    return f"Answer:\n{answer_text.strip()}"


def strip_code_fence(reply: str) -> str:
    m = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", reply, flags=re.DOTALL)
    return m.group(1) if m else reply.strip()


def parse_claims(reply: str, answer_id: str) -> list[Claim]:
    """Validate a model reply and return Claims with ids like q01-c01."""
    try:
        data = json.loads(strip_code_fence(reply))
    except json.JSONDecodeError as e:
        raise ExtractionError(f"reply is not valid JSON: {e}") from e
    if not isinstance(data, list) or not data:
        raise ExtractionError("reply must be a non-empty JSON array")
    claims = []
    for i, item in enumerate(data, start=1):
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            raise ExtractionError(f"item {i} must be an object with a string 'text'")
        if not item["text"].strip():
            raise ExtractionError(f"item {i} has empty text")
        try:
            citation = normalize_citation_id(item.get("citation"))
        except ValueError as e:
            raise ExtractionError(f"item {i}: {e}") from e
        claims.append(Claim(f"{answer_id}-c{i:02d}", item["text"].strip(), citation))
    return claims


def extract_claims(answer_id: str, answer_text: str, client: LLMClient) -> list[Claim]:
    """Ask the model to split the answer, then validate its reply."""
    reply = client.complete(SYSTEM_PROMPT, build_user_prompt(answer_text))
    return parse_claims(reply, answer_id)
