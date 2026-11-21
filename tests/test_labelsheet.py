import csv
import json
from pathlib import Path

import pytest

from claimcheck import labelsheet as ls


@pytest.fixture
def env(tmp_path: Path):
    topics = tmp_path / "topics.json"
    topics.write_text(
        json.dumps(
            [
                {"answer_id": "q01", "split": "dev", "sources": [{"source_id": "S1"}]},
                {"answer_id": "q02", "split": "test", "sources": [{"source_id": "S1"}]},
            ]
        ),
        encoding="utf-8",
    )
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "q01_S1.txt").write_text("x", encoding="utf-8")
    (sources / "q02_S1.txt").write_text("x", encoding="utf-8")
    raw = tmp_path / "raw.csv"
    # BOM on purpose: spreadsheet apps often add one when exporting CSV.
    raw.write_text(
        "﻿claim_id,answer_id,claim_text,citation_id\n"
        'q01-c01,q01,"It has gears, many of them.",S1\n'
        "q02-c01,q02,It is old.,S1\n",
        encoding="utf-8",
    )
    return tmp_path, topics, sources, raw


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_build_adds_split_and_defaults_and_handles_bom_and_commas(env):
    tmp, topics, _, raw = env
    out = tmp / "labels.csv"
    assert ls.build_sheet(raw, topics, out) == 2
    rows = _rows(out)
    assert rows[0]["split"] == "dev" and rows[1]["split"] == "test"
    assert rows[0]["claim_text"] == "It has gears, many of them."
    assert rows[0]["origin"] == "organic" and rows[0]["label"] == ""


def test_build_refuses_to_overwrite_existing_labels(env):
    tmp, topics, _, raw = env
    out = tmp / "labels.csv"
    ls.build_sheet(raw, topics, out)
    with pytest.raises(FileExistsError):
        ls.build_sheet(raw, topics, out)


def test_build_rejects_unknown_answer_id(env):
    tmp, topics, _, raw = env
    raw.write_text("claim_id,answer_id,claim_text,citation_id\nx,q99,t,S1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        ls.build_sheet(raw, topics, tmp / "labels.csv")


def test_validate_clean_sheet_counts_unlabeled(env):
    tmp, topics, sources, raw = env
    out = tmp / "labels.csv"
    ls.build_sheet(raw, topics, out)
    problems, stats = ls.validate_sheet(out, sources, topics)
    assert problems == []
    assert stats["by_label"] == {"UNLABELED": 2}


def _edit(path: Path, **changes_by_claim):
    rows = _rows(path)
    for r in rows:
        r.update(changes_by_claim.get(r["claim_id"], {}))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ls.COLUMNS)
        w.writeheader()
        w.writerows(rows)


def test_validate_flags_bad_label_and_long_quote(env):
    tmp, topics, sources, raw = env
    out = tmp / "labels.csv"
    ls.build_sheet(raw, topics, out)
    _edit(
        out,
        **{
            "q01-c01": {"label": "maybe"},
            "q02-c01": {"label": "supported", "evidence_quote": "w " * 16},
        },
    )
    problems, stats = ls.validate_sheet(out, sources, topics)
    assert any("invalid label" in p for p in problems)
    # An over-long quote is a warning, not an error: quotes feed no metric.
    assert not any("longer than" in p for p in problems)
    assert any("longer than" in w for w in stats["warnings"])


def test_validate_enforces_citation_missing_rule(env):
    tmp, topics, sources, raw = env
    out = tmp / "labels.csv"
    ls.build_sheet(raw, topics, out)
    _edit(
        out,
        **{
            # Source S1 exists, so CITATION_MISSING is wrong here.
            "q01-c01": {"label": "CITATION_MISSING"},
            # Source S9 does not exist, so SUPPORTED is wrong here.
            "q02-c01": {"label": "SUPPORTED", "citation_id": "S9"},
        },
    )
    problems, _ = ls.validate_sheet(out, sources, topics)
    assert any("CITATION_MISSING but source" in p for p in problems)
    assert any("no such source" in p for p in problems)


def test_validate_requires_planted_type_for_planted_rows(env):
    tmp, topics, sources, raw = env
    out = tmp / "labels.csv"
    ls.build_sheet(raw, topics, out)
    _edit(out, **{"q01-c01": {"origin": "planted", "planted_type": ""}})
    problems, _ = ls.validate_sheet(out, sources, topics)
    assert any("planted rows need planted_type" in p for p in problems)


def _two_source_env(tmp: Path, s1_rows: int, s2_rows: int):
    topics = tmp / "topics2.json"
    topics.write_text(
        json.dumps(
            [
                {
                    "answer_id": "q01",
                    "split": "dev",
                    "sources": [{"source_id": "S1"}, {"source_id": "S2"}],
                }
            ]
        ),
        encoding="utf-8",
    )
    sources = tmp / "sources2"
    sources.mkdir()
    for sid in ("S1", "S2"):
        (sources / f"q01_{sid}.txt").write_text("x", encoding="utf-8")
    lines = ["claim_id,answer_id,claim_text,citation_id"]
    lines += [f"q01-a{i},q01,fact {i},S1" for i in range(s1_rows)]
    lines += [f"q01-b{i},q01,fact {i},S2" for i in range(s2_rows)]
    raw = tmp / "raw2.csv"
    raw.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = tmp / "labels2.csv"
    ls.build_sheet(raw, topics, out)
    return out, sources, topics


def test_validate_flags_skewed_citation_balance(tmp_path: Path):
    # Reproduces the real failure: 71 claims cite S1 and 1 cites S2.
    out, sources, topics = _two_source_env(tmp_path, s1_rows=71, s2_rows=1)
    problems, stats = ls.validate_sheet(out, sources, topics)
    assert any("citation imbalance: S2" in p for p in problems)
    assert stats["by_citation_organic"] == {"S1": 71, "S2": 1}


def test_validate_accepts_balanced_citations(tmp_path: Path):
    out, sources, topics = _two_source_env(tmp_path, s1_rows=36, s2_rows=36)
    problems, _ = ls.validate_sheet(out, sources, topics)
    assert problems == []


def test_fix_splits_changes_only_the_split_column_and_is_idempotent(env):
    tmp, topics, sources, raw = env
    out = tmp / "labels.csv"
    ls.build_sheet(raw, topics, out)
    _edit(
        out,
        **{"q02-c01": {"split": "dev", "label": "SUPPORTED", "notes": "keep me"}},  # wrong: test
    )
    before = {r["claim_id"]: r for r in _rows(out)}
    assert ls.fix_splits(out, topics) == [("q02-c01", "dev", "test")]
    after = {r["claim_id"]: r for r in _rows(out)}
    assert after["q02-c01"]["split"] == "test"
    for cid, row in after.items():  # everything else is untouched
        assert {k: v for k, v in row.items() if k != "split"} == {
            k: v for k, v in before[cid].items() if k != "split"
        }
    assert ls.fix_splits(out, topics) == []  # second run: nothing to do
    problems, _ = ls.validate_sheet(out, sources, topics)
    assert problems == []
