import csv
from pathlib import Path

import pytest

from claimcheck.dataset import load_examples, load_sources
from claimcheck.labelsheet import COLUMNS
from claimcheck.schema import Label


def _write_sheet(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})


def _row(claim_id, split="dev", label="SUPPORTED", **extra):
    base = {
        "claim_id": claim_id,
        "answer_id": claim_id.split("-")[0],
        "split": split,
        "claim_text": f"text of {claim_id}",
        "citation_id": "S1",
        "origin": "organic",
        "label": label,
    }
    return {**base, **extra}


def test_load_sources_strips_headers_and_groups_by_answer(tmp_path: Path):
    for name, body in [("q01_S1", "one"), ("q01_S2", "two"), ("q02_S1", "three")]:
        (tmp_path / f"{name}.txt").write_text(f"# Source\n---\n{body}\n", encoding="utf-8")
    assert load_sources(tmp_path) == {"q01": {"S1": "one", "S2": "two"}, "q02": {"S1": "three"}}


def test_load_examples_parses_labels_and_planted_fields(tmp_path: Path):
    sheet = tmp_path / "labels.csv"
    _write_sheet(
        sheet,
        [
            _row("q01-c01"),
            _row(
                "q01-p01",
                label="citation missing",
                origin="planted",
                planted_type="fake_citation",
                citation_id="S3",
            ),
        ],
    )
    a, b = load_examples(sheet)
    assert a.gold is Label.SUPPORTED and a.claim.citation_id == "S1"
    assert b.gold is Label.CITATION_MISSING and b.planted_type == "fake_citation"


def test_split_filter_keeps_only_requested_split(tmp_path: Path):
    sheet = tmp_path / "labels.csv"
    _write_sheet(sheet, [_row("q01-c01", "dev"), _row("q02-c01", "test")])
    assert [e.claim.claim_id for e in load_examples(sheet, split="test")] == ["q02-c01"]


def test_unlabeled_rows_raise_unless_allowed(tmp_path: Path):
    sheet = tmp_path / "labels.csv"
    _write_sheet(sheet, [_row("q01-c01", label="")])
    with pytest.raises(ValueError):
        load_examples(sheet)
    assert load_examples(sheet, require_labels=False)[0].gold is None
