from types import SimpleNamespace as NS

import pytest

from claimcheck.anthropic_client import AnthropicClient, ReplyTruncated
from claimcheck.cost import (
    HAIKU_5_5,
    SONNET_5_5,
    Pricing,
    estimate_judge_run,
    estimate_run,
    estimate_tokens,
)
from claimcheck.dataset import Example
from claimcheck.schema import Claim, Label


class FakeSDK:
    """Stands in for anthropic.Anthropic(): records create() kwargs, returns a canned response."""

    def __init__(self, content, stop_reason="end_turn", thinking_tokens=0, usage=(100, 20)):
        self.kwargs = None
        self._resp = NS(
            content=content,
            stop_reason=stop_reason,
            usage=NS(
                input_tokens=usage[0],
                output_tokens=usage[1],
                output_tokens_details=NS(thinking_tokens=thinking_tokens),
            ),
        )
        self.messages = NS(create=self._create)

    def _create(self, **kwargs):
        self.kwargs = kwargs
        return self._resp


def text_block(t):
    return NS(type="text", text=t)


def test_complete_sends_expected_request_and_never_sends_temperature():
    sdk = FakeSDK([text_block("hello")])
    c = AnthropicClient(model="claude-haiku-5-5", max_tokens=300, sdk=sdk)
    assert c.complete("be brief", "hi") == "hello"
    assert sdk.kwargs == {
        "model": "claude-haiku-5-5",
        "max_tokens": 300,
        "system": "be brief",
        "messages": [{"role": "user", "content": "hi"}],
    }


def test_usage_accumulates_and_cost_is_computed_from_measured_tokens():
    sdk = FakeSDK([text_block("a")], usage=(1_000_000, 1_000_000), thinking_tokens=7)
    c = AnthropicClient(sdk=sdk)
    c.complete("s", "u")
    assert (c.input_tokens, c.output_tokens, c.thinking_tokens) == (1_000_000, 1_000_000, 7)
    assert c.spent_usd(HAIKU_5_5) == pytest.approx(0.10 + 0.50)


def test_thinking_blocks_are_ignored_and_text_blocks_joined():
    sdk = FakeSDK([NS(type="thinking", thinking="hmm"), text_block("A"), text_block("B")])
    assert AnthropicClient(sdk=sdk).complete("s", "u") == "AB"


def test_truncated_reply_raises_but_is_still_counted_as_spend():
    sdk = FakeSDK([text_block("cut o")], stop_reason="max_tokens")
    c = AnthropicClient(sdk=sdk)
    with pytest.raises(ReplyTruncated):
        c.complete("s", "u")
    assert c.calls == 1 and c.output_tokens == 20  # billed even though unusable


def test_empty_reply_raises():
    with pytest.raises(ValueError):
        AnthropicClient(sdk=FakeSDK([NS(type="thinking", thinking="only thoughts")])).complete(
            "s", "u"
        )


def test_extra_params_are_passed_through():
    sdk = FakeSDK([text_block("x")])
    AnthropicClient(sdk=sdk, extra_params={"thinking": {"type": "disabled"}}).complete("s", "u")
    assert sdk.kwargs["thinking"] == {"type": "disabled"}


def test_pricing_arithmetic_and_known_rates():
    assert Pricing("m", 2.0, 10.0).cost(500_000, 100_000) == pytest.approx(1.0 + 1.0)
    assert (HAIKU_5_5.input_per_mtok, HAIKU_5_5.output_per_mtok) == (0.10, 0.50)
    assert (SONNET_5_5.input_per_mtok, SONNET_5_5.output_per_mtok) == (2.00, 10.00)


def test_estimate_tokens_is_about_four_chars_per_token():
    assert estimate_tokens("a" * 400) == 100


def test_estimate_run_expected_is_below_worst_case():
    e = estimate_run([("s" * 40, "u" * 4000)] * 10, HAIKU_5_5)
    assert e.calls == 10 and e.input_tokens == 10 * (10 + 1000)
    assert 0 < e.expected_usd < e.worst_case_usd


def test_judge_estimate_skips_claims_that_never_reach_the_judge():
    sources = {"q01": {"S1": "text " * 100}}
    ex = lambda cid, cit: Example(  # noqa: E731
        Claim(cid, "claim", cit), "q01", "dev", "organic", "", Label.SUPPORTED
    )
    examples = [ex("a", "S1"), ex("b", "S9"), ex("c", None)]  # only "a" costs money
    assert estimate_judge_run(examples, sources, HAIKU_5_5).calls == 1
