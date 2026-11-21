import json
from datetime import date
from pathlib import Path

import pytest

from claimcheck import wikisource as ws

PAYLOAD = {
    "query": {
        "pages": [
            {
                "pageid": 7,
                "title": "Astrolabe",
                "revisions": [{"revid": 12345}],
                "extract": (
                    "An astrolabe is an instrument.\n"
                    "It models the sky.\n\n\n"
                    "== History ==\n"
                    "Used in antiquity. " + "word " * 50 + "\n\n\n"
                    "== See also ==\n"
                    "Quadrant"
                ),
            }
        ]
    }
}


def test_parse_response_extracts_title_revision_and_text():
    page = ws.parse_response(PAYLOAD)
    assert (page.title, page.pageid, page.revid) == ("Astrolabe", 7, 12345)
    assert page.permalink.endswith("title=Astrolabe&oldid=12345")


def test_parse_response_raises_for_missing_page():
    with pytest.raises(LookupError):
        ws.parse_response({"query": {"pages": [{"title": "Nope", "missing": True}]}})


def test_build_url_encodes_title_and_sets_required_params():
    url = ws.build_url("Tacoma Narrows Bridge (1940)")
    assert "titles=Tacoma+Narrows+Bridge+%281940%29" in url
    assert "explaintext=1" in url and "redirects=1" in url


def test_truncate_cuts_at_paragraph_boundary_and_drops_tail_sections():
    text = ws.parse_response(PAYLOAD).text
    out = ws.truncate_words(text, max_words=1000)
    assert "See also" not in out and "Quadrant" not in out
    assert "Used in antiquity" in out


def test_truncate_respects_word_budget_and_never_ends_on_heading():
    text = "First paragraph here.\n== Middle ==\n" + "x " * 100
    out = ws.truncate_words(text, max_words=10)
    assert out == "First paragraph here."


def test_truncate_always_keeps_first_paragraph_even_if_over_budget():
    out = ws.truncate_words("one two three four five six", max_words=2)
    assert out == "one two three four five six"


def test_write_then_read_source_roundtrip_with_provenance(tmp_path: Path):
    page = ws.parse_response(PAYLOAD)
    path = ws.write_source(page, "q01", "S2", tmp_path, 700, retrieved=date(2026, 11, 20))
    assert path.name == "q01_S2.txt"
    raw = path.read_text(encoding="utf-8")
    assert "oldid=12345" in raw and "CC BY-SA 4.0" in raw and "2026-11-20" in raw
    body = ws.read_source(path)
    assert body.startswith("An astrolabe") and "# Source" not in body


def test_read_source_rejects_file_without_header(tmp_path: Path):
    p = tmp_path / "bad.txt"
    p.write_text("no header here", encoding="utf-8")
    with pytest.raises(ValueError):
        ws.read_source(p)


def test_fetch_all_uses_injected_http_and_writes_files(tmp_path: Path):
    calls = []

    def fake_get(url: str) -> dict:
        calls.append(url)
        return PAYLOAD

    topics = [
        {
            "answer_id": "q01",
            "split": "dev",
            "sources": [{"source_id": "S1", "title": "Astrolabe"}],
        }
    ]
    paths = ws.fetch_all(topics, tmp_path, 700, http_get=fake_get, delay_s=0)
    assert len(calls) == 1 and paths[0].exists()


def test_committed_topics_file_is_valid_and_split_is_reasonable():
    topics = ws.load_topics(Path(__file__).parent.parent / "eval" / "topics.json")
    assert len(topics) == 12
    dev = sum(t["split"] == "dev" for t in topics)
    assert 3 <= dev <= 5
    assert all(len(t["sources"]) == 2 for t in topics)


def test_with_retries_backs_off_then_succeeds():
    attempts, sleeps = [], []

    def flaky(url: str) -> dict:
        attempts.append(url)
        if len(attempts) < 3:
            raise ws.RateLimited(retry_after=1)
        return {"ok": True}

    assert ws.with_retries(flaky, "u", sleep=sleeps.append) == {"ok": True}
    assert sleeps == [1.0, 2.0]  # exponential: 1*2^0, 1*2^1


def test_with_retries_gives_up_after_max_tries():
    def always(url: str) -> dict:
        raise ws.RateLimited(retry_after=1)

    with pytest.raises(ws.RateLimited):
        ws.with_retries(always, "u", max_tries=3, sleep=lambda s: None)


def test_load_topics_rejects_bad_split(tmp_path: Path):
    p = tmp_path / "t.json"
    p.write_text(json.dumps([{"answer_id": "q1", "split": "val", "sources": []}]), encoding="utf-8")
    with pytest.raises(ValueError):
        ws.load_topics(p)
