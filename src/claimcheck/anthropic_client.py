"""The real LLM client, backed by Anthropic's official Python SDK.

Verified against the official docs and the installed SDK on 2026-11-20:
- Model id for the cheapest current model: "claude-haiku-5-5".
- messages.create accepts model, max_tokens, system, messages (and thinking, output_config).
- It has no named temperature parameter in this SDK version, so none is sent. Reproducibility
  comes from CachedClient, which replays stored replies.
- Whether Haiku 5.5 thinks by default is NOT documented. Thinking tokens are billed as output
  and count toward max_tokens, so this client (1) caps output at max_tokens, (2) raises
  ReplyTruncated instead of returning a cut-off reply, and (3) records thinking tokens so a
  smoke test shows whether they occur. `extra_params` lets you pass settings such as
  {"thinking": {"type": "disabled"}} without a code change, if the model supports them.

The API key is read from the ANTHROPIC_API_KEY environment variable by the SDK. It is never
printed, logged, or stored by this code.
"""

from __future__ import annotations

from typing import Any

from claimcheck.cost import HAIKU_5_5, Pricing

DEFAULT_MODEL = "claude-haiku-5-5"


class ReplyTruncated(RuntimeError):
    """The reply hit max_tokens, so it may be cut off. Never parse a truncated reply."""


class AnthropicClient:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 1500,
        sdk: Any = None,
        extra_params: dict | None = None,
    ):
        if sdk is None:
            try:
                import anthropic
            except ImportError as e:
                raise RuntimeError("install the SDK first: pip install -e '.[llm]'") from e
            sdk = anthropic.Anthropic()
        self.sdk = sdk
        self.model = model
        self.max_tokens = max_tokens
        self.extra_params = dict(extra_params or {})
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.thinking_tokens = 0
        self.last_stop_reason: str | None = None

    def complete(self, system: str, user: str) -> str:
        resp = self.sdk.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            **self.extra_params,
        )
        # Count usage first: a truncated reply was still billed. Prompt caching is not used, so
        # only plain input and output tokens are tracked.
        self.calls += 1
        self.input_tokens += resp.usage.input_tokens
        self.output_tokens += resp.usage.output_tokens
        details = getattr(resp.usage, "output_tokens_details", None)
        self.thinking_tokens += getattr(details, "thinking_tokens", 0) or 0
        self.last_stop_reason = resp.stop_reason
        if resp.stop_reason == "max_tokens":
            raise ReplyTruncated(f"reply hit max_tokens={self.max_tokens}")
        text = "".join(b.text for b in resp.content if b.type == "text")
        if not text.strip():
            raise ValueError("model returned no text")
        return text

    def spent_usd(self, pricing: Pricing = HAIKU_5_5) -> float:
        """Measured cost of every real call made so far, from the API's own token counts."""
        return pricing.cost(self.input_tokens, self.output_tokens)


def main() -> None:
    """One tiny real call (well under $0.001). Run once to confirm your key and the reply shape."""
    client = AnthropicClient()
    reply = client.complete("Reply with exactly the single word: ok", "ping")
    print(f"reply: {reply!r}")
    print(f"stop_reason: {client.last_stop_reason}")
    print(f"tokens: input={client.input_tokens} output={client.output_tokens}")
    print(f"thinking tokens in output: {client.thinking_tokens}")
    print(f"cost: ${client.spent_usd():.6f}")


if __name__ == "__main__":
    main()
