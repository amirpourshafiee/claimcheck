"""LLM plumbing: a tiny client interface, a disk cache, and a hard cap on paid calls.

Every pipeline stage takes an `LLMClient` as an argument (dependency injection). Unit tests pass a
`ScriptedClient`, so they are free and deterministic. A real provider client is added later and
wrapped in `CachedClient`, which gives reproducible reruns and enforces the call budget.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Send one prompt, return the model's text reply."""
        ...


class CallBudgetExceeded(RuntimeError):
    """Raised before a paid call that would exceed the configured cap."""


class ScriptedClient:
    """Test double. Replies come from a list (in order) or a function of (system, user).

    Records every prompt in `.calls`, so tests can assert on what was sent.
    """

    def __init__(self, replies: list[str] | Callable[[str, str], str]):
        self._replies = replies
        self._i = 0
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if callable(self._replies):
            return self._replies(system, user)
        if self._i >= len(self._replies):
            raise AssertionError("ScriptedClient ran out of scripted replies")
        reply = self._replies[self._i]
        self._i += 1
        return reply


class CachedClient:
    """Wrap a client with an on-disk cache and a cap on real (uncached) calls.

    - Cache key = hash of (model_id, system, user). Changing the prompt or model misses the cache.
    - Cache hits are free and do not count toward the cap.
    - Failures are never cached: if the inner client raises, nothing is written.
    - The cap is checked BEFORE the call, so a run can never overshoot it.
    """

    def __init__(
        self,
        inner: LLMClient,
        model_id: str,
        cache_dir: Path = Path(".claimcheck_cache"),
        max_calls: int = 200,
    ):
        self.inner = inner
        self.model_id = model_id
        self.cache_dir = Path(cache_dir)
        self.max_calls = max_calls
        self.calls_made = 0
        self.cache_hits = 0

    def _key(self, system: str, user: str) -> str:
        payload = json.dumps([self.model_id, system, user], ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def complete(self, system: str, user: str) -> str:
        path = self.cache_dir / f"{self._key(system, user)}.json"
        if path.exists():
            self.cache_hits += 1
            return json.loads(path.read_text(encoding="utf-8"))["reply"]
        if self.calls_made >= self.max_calls:
            raise CallBudgetExceeded(
                f"refusing call {self.calls_made + 1}: cap is {self.max_calls} real calls"
            )
        reply = self.inner.complete(system, user)
        self.calls_made += 1
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Write to a temp file, then rename, so a crash never leaves a half-written cache entry.
        fd, tmp = tempfile.mkstemp(dir=self.cache_dir, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"model_id": self.model_id, "reply": reply}, f, ensure_ascii=False)
        os.replace(tmp, path)
        return reply
