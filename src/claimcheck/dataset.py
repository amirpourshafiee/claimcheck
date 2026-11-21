"""Load the hand-labeled dataset (labels.csv) and the source excerpts into typed objects."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from claimcheck.schema import Claim, Label
from claimcheck.wikisource import read_source


@dataclass(frozen=True)
class Example:
    claim: Claim
    answer_id: str
    split: str  # "dev" or "test"
    origin: str  # "organic" or "planted"
    planted_type: str  # "" for organic rows
    gold: Label | None  # None when the row is not labeled yet


def load_sources(sources_dir: Path) -> dict[str, dict[str, str]]:
    """Map answer_id -> {source_id: excerpt text}, from files named like q01_S1.txt."""
    out: dict[str, dict[str, str]] = {}
    for path in sorted(Path(sources_dir).glob("*.txt")):
        answer_id, _, source_id = path.stem.rpartition("_")
        out.setdefault(answer_id, {})[source_id] = read_source(path)
    return out


def load_examples(
    sheet_path: Path, split: str | None = None, require_labels: bool = True
) -> list[Example]:
    """Read labels.csv. Optionally keep one split. Raises if require_labels and a row is blank."""
    with Path(sheet_path).open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    examples = []
    for r in rows:
        if split is not None and r["split"] != split:
            continue
        raw_label = (r.get("label") or "").strip()
        if not raw_label and require_labels:
            raise ValueError(f"{r['claim_id']} is not labeled yet")
        examples.append(
            Example(
                claim=Claim(
                    r["claim_id"].strip(),
                    r["claim_text"].strip(),
                    r["citation_id"].strip() or None,
                ),
                answer_id=r["answer_id"].strip(),
                split=r["split"].strip(),
                origin=r["origin"].strip(),
                planted_type=(r.get("planted_type") or "").strip(),
                gold=Label.parse(raw_label) if raw_label else None,
            )
        )
    return examples
