import json

import pytest

from claimcheck.llm import CachedClient, CallBudgetExceeded, ScriptedClient


def test_scripted_client_returns_replies_in_order_and_records_prompts():
    c = ScriptedClient(["a", "b"])
    assert (c.complete("sys", "u1"), c.complete("sys", "u2")) == ("a", "b")
    assert c.calls == [("sys", "u1"), ("sys", "u2")]


def test_scripted_client_fails_loudly_when_script_runs_out():
    c = ScriptedClient(["only one"])
    c.complete("s", "u")
    with pytest.raises(AssertionError):
        c.complete("s", "u")


def test_cache_hit_skips_inner_call_and_does_not_count(tmp_path):
    inner = ScriptedClient(["reply"])
    c = CachedClient(inner, "model-x", cache_dir=tmp_path)
    assert c.complete("s", "u") == "reply"
    assert c.complete("s", "u") == "reply"  # inner has no second scripted reply: must be a hit
    assert (c.calls_made, c.cache_hits, len(inner.calls)) == (1, 1, 1)


def test_cache_key_changes_with_prompt_and_model(tmp_path):
    inner = ScriptedClient(lambda s, u: f"{s}|{u}")
    CachedClient(inner, "m1", cache_dir=tmp_path).complete("s", "u")
    CachedClient(inner, "m2", cache_dir=tmp_path).complete("s", "u")  # different model
    CachedClient(inner, "m1", cache_dir=tmp_path).complete("s", "other")  # different prompt
    assert len(inner.calls) == 3


def test_cap_blocks_the_call_before_it_is_made(tmp_path):
    inner = ScriptedClient(lambda s, u: "ok")
    c = CachedClient(inner, "m", cache_dir=tmp_path, max_calls=2)
    c.complete("s", "1")
    c.complete("s", "2")
    with pytest.raises(CallBudgetExceeded):
        c.complete("s", "3")
    assert len(inner.calls) == 2  # the third call never reached the inner client


def test_cache_hits_are_allowed_even_after_the_cap_is_reached(tmp_path):
    inner = ScriptedClient(lambda s, u: "ok")
    c = CachedClient(inner, "m", cache_dir=tmp_path, max_calls=1)
    c.complete("s", "1")
    assert c.complete("s", "1") == "ok"  # cached, so free


def test_failed_calls_are_not_cached_or_counted(tmp_path):
    def boom(s, u):
        raise RuntimeError("network down")

    c = CachedClient(ScriptedClient(boom), "m", cache_dir=tmp_path)
    with pytest.raises(RuntimeError):
        c.complete("s", "u")
    assert c.calls_made == 0 and list(tmp_path.glob("*.json")) == []


def test_cache_file_stores_model_and_reply_only(tmp_path):
    c = CachedClient(ScriptedClient(["r"]), "model-x", cache_dir=tmp_path)
    c.complete("secret system prompt", "u")
    (f,) = tmp_path.glob("*.json")
    assert json.loads(f.read_text()) == {"model_id": "model-x", "reply": "r"}
