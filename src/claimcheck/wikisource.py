"""Fetch plain-text Wikipedia excerpts to use as cited sources in the labeled dataset.

Wikipedia text is licensed CC BY-SA 4.0. Every saved file records the page title, the exact
revision (so the excerpt is reproducible), the license, and the retrieval date.

Wikimedia asks API clients to send a descriptive User-Agent and to be gentle with request
rates. This module does both. Set CLAIMCHECK_USER_AGENT to override the default.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

API = "https://en.wikipedia.org/w/api.php"
DEFAULT_USER_AGENT = "claimcheck/0.1 (portfolio project; contact: amir@users.noreply.github.com)"
HEADER_END = "---"
# Sections that carry no prose. Everything from the first one onward is dropped.
TAIL_SECTIONS = {
    "see also",
    "notes",
    "references",
    "citations",
    "further reading",
    "external links",
    "bibliography",
    "sources",
}

HttpGet = Callable[[str], dict]


@dataclass(frozen=True)
class Page:
    title: str
    pageid: int
    revid: int
    text: str

    @property
    def permalink(self) -> str:
        title = urllib.parse.quote(self.title.replace(" ", "_"))
        return f"https://en.wikipedia.org/w/index.php?title={title}&oldid={self.revid}"


def build_url(title: str) -> str:
    params = {
        "action": "query",
        "prop": "extracts|revisions",
        "explaintext": 1,
        "redirects": 1,
        "rvprop": "ids",
        "format": "json",
        "formatversion": 2,
        "titles": title,
    }
    return f"{API}?{urllib.parse.urlencode(params)}"


def parse_response(payload: dict) -> Page:
    """Turn a MediaWiki API payload (formatversion=2) into a Page. Raises LookupError if absent."""
    pages = payload.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        raise LookupError("Wikipedia page not found")
    p = pages[0]
    return Page(
        title=p["title"],
        pageid=p["pageid"],
        revid=p["revisions"][0]["revid"],
        text=p.get("extract", ""),
    )


def _is_heading(line: str) -> bool:
    return line.startswith("==") and line.endswith("==")


def _heading_name(line: str) -> str:
    return line.strip("= ").strip().lower()


def truncate_words(text: str, max_words: int) -> str:
    """Keep whole paragraphs from the start of the text, up to max_words words.

    Always keeps at least the first paragraph. Cuts at the first non-prose tail section (for
    example "See also"). Never ends on a dangling section heading.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    kept: list[str] = []
    words = 0
    for ln in lines:
        if _is_heading(ln) and _heading_name(ln) in TAIL_SECTIONS:
            break
        n = len(ln.split())
        if kept and words + n > max_words:
            break
        kept.append(ln)
        words += n
    while kept and _is_heading(kept[-1]):
        kept.pop()
    return "\n\n".join(kept)


def write_source(
    page: Page,
    answer_id: str,
    source_id: str,
    out_dir: Path,
    max_words: int,
    retrieved: date | None = None,
) -> Path:
    """Write one excerpt file with a provenance header. Returns the path."""
    retrieved = retrieved or date.today()
    body = truncate_words(page.text, max_words)
    header = [
        f"# Source: {source_id} | {page.title}",
        f"# URL: {page.permalink}",
        "# License: CC BY-SA 4.0 (Wikipedia contributors)",
        f"# Excerpt: first {len(body.split())} words, whole paragraphs only",
        f"# Retrieved: {retrieved.isoformat()}",
        HEADER_END,
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{answer_id}_{source_id}.txt"
    path.write_text("\n".join(header) + "\n" + body + "\n", encoding="utf-8")
    return path


def read_source(path: Path) -> str:
    """Return only the excerpt body, without the provenance header."""
    text = path.read_text(encoding="utf-8")
    head, sep, body = text.partition(f"\n{HEADER_END}\n")
    if not sep:
        raise ValueError(f"{path} has no provenance header terminated by '{HEADER_END}'")
    return body.strip()


def load_topics(path: Path) -> list[dict]:
    """Load and validate eval/topics.json."""
    topics = json.loads(path.read_text(encoding="utf-8"))
    ids = [t["answer_id"] for t in topics]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate answer_id in topics file")
    for t in topics:
        if t["split"] not in {"dev", "test"}:
            raise ValueError(f"{t['answer_id']}: split must be 'dev' or 'test'")
        sids = [s["source_id"] for s in t["sources"]]
        if len(sids) != len(set(sids)):
            raise ValueError(f"{t['answer_id']}: duplicate source_id")
    return topics


class RateLimited(Exception):
    """The server asked us to slow down (HTTP 429 or 503)."""

    def __init__(self, retry_after: float):
        super().__init__(f"rate limited, retry after {retry_after}s")
        self.retry_after = retry_after


def _fetch_once(url: str) -> dict:
    ua = os.environ.get("CLAIMCHECK_USER_AGENT", DEFAULT_USER_AGENT)
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (fixed https API)
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (429, 503):
            try:
                retry_after = float(e.headers.get("Retry-After", 2))
            except (TypeError, ValueError):
                retry_after = 2.0  # Retry-After can also be an HTTP date; fall back
            raise RateLimited(retry_after) from e
        raise


def with_retries(
    fetch: HttpGet,
    url: str,
    max_tries: int = 6,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Call fetch(url), honoring Retry-After with exponential backoff (capped at 30 s)."""
    for attempt in range(max_tries):
        try:
            return fetch(url)
        except RateLimited as e:
            if attempt == max_tries - 1:
                raise
            sleep(min(max(e.retry_after, 1.0) * 2**attempt, 30.0))
    raise AssertionError("unreachable")


def default_http_get(url: str) -> dict:
    return with_retries(_fetch_once, url)


def fetch_all(
    topics: list[dict],
    out_dir: Path,
    max_words: int,
    http_get: HttpGet = default_http_get,
    delay_s: float = 1.0,
) -> list[Path]:
    paths = []
    for t in topics:
        for s in t["sources"]:
            page = parse_response(http_get(build_url(s["title"])))
            paths.append(write_source(page, t["answer_id"], s["source_id"], out_dir, max_words))
            time.sleep(delay_s)
    return paths


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Fetch Wikipedia excerpts for the dataset.")
    ap.add_argument("topics", type=Path)
    ap.add_argument("--out", type=Path, default=Path("eval/sources"))
    ap.add_argument("--max-words", type=int, default=700)
    args = ap.parse_args(argv)
    paths = fetch_all(load_topics(args.topics), args.out, args.max_words)
    print(f"Wrote {len(paths)} source files to {args.out}")


if __name__ == "__main__":
    main()
