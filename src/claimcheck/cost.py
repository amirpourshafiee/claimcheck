"""Price tables and cost estimation, so every paid run starts with a number, not a surprise.

Prices are USD per million tokens (MTok) for prompts up to 100,000 tokens, copied from the
official pricing page on PRICING_CHECKED. Prices change: re-check before trusting them.
Estimates use a rough rule (about 4 characters per token for English). The real count is
measured from the API's usage fields after each call, and that measured number is the one to
report.
"""

from __future__ import annotations

import argparse
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

PRICING_CHECKED = "2026-11-20, https://platform.claude.com/docs/en/about-claude/pricing"


@dataclass(frozen=True)
class Pricing:
    model: str
    input_per_mtok: float
    output_per_mtok: float

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens * self.input_per_mtok + output_tokens * self.output_per_mtok) / 1e6


HAIKU_5_5 = Pricing("claude-haiku-5-5", 0.10, 0.50)
SONNET_5_5 = Pricing("claude-sonnet-5-5", 2.00, 10.00)


def estimate_tokens(text: str) -> int:
    """Rough token count: about 4 characters per token. Good for budgeting, not billing."""
    return math.ceil(len(text) / 4)


@dataclass(frozen=True)
class CostEstimate:
    calls: int
    input_tokens: int
    expected_output_tokens: int
    expected_usd: float
    worst_case_usd: float  # if every call used its full max_tokens


def estimate_run(
    prompts: Sequence[tuple[str, str]],
    pricing: Pricing,
    expected_output_tokens: int = 150,
    max_output_tokens: int = 1500,
) -> CostEstimate:
    """Estimate one run over (system, user) prompt pairs. Assumes zero cache hits."""
    input_tokens = sum(estimate_tokens(s) + estimate_tokens(u) for s, u in prompts)
    n = len(prompts)
    return CostEstimate(
        calls=n,
        input_tokens=input_tokens,
        expected_output_tokens=n * expected_output_tokens,
        expected_usd=pricing.cost(input_tokens, n * expected_output_tokens),
        worst_case_usd=pricing.cost(input_tokens, n * max_output_tokens),
    )


def estimate_judge_run(examples, sources: dict[str, dict[str, str]], pricing: Pricing, **kw):
    """Estimate judging every example. Claims with a missing or absent citation cost nothing."""
    from claimcheck.judge import SYSTEM_PROMPT, build_user_prompt  # local: avoids import cycles

    prompts = []
    for ex in examples:
        text = sources.get(ex.answer_id, {}).get(ex.claim.citation_id or "")
        if text is not None:
            prompts.append((SYSTEM_PROMPT, build_user_prompt(ex.claim, text)))
    return estimate_run(prompts, pricing, **kw)


def main(argv: list[str] | None = None) -> None:
    from claimcheck.dataset import load_examples, load_sources

    ap = argparse.ArgumentParser(description="Estimate the cost of one judging run (no API calls).")
    ap.add_argument("--sheet", type=Path, default=Path("eval/dataset/labels.csv"))
    ap.add_argument("--sources", type=Path, default=Path("eval/sources"))
    args = ap.parse_args(argv)
    examples = load_examples(args.sheet, require_labels=False)
    sources = load_sources(args.sources)
    print(f"Prices checked: {PRICING_CHECKED}")
    for p in (HAIKU_5_5, SONNET_5_5):
        e = estimate_judge_run(examples, sources, p)
        print(
            f"{p.model}: {e.calls} calls, ~{e.input_tokens:,} input tokens, "
            f"expected ${e.expected_usd:.3f}, worst case ${e.worst_case_usd:.3f} per full run"
        )


if __name__ == "__main__":
    main()
