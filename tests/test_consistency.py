import csv

import pytest

from claimcheck.consistency import compare, pick_sample, write_blind_sample

HEADER = (
    "claim_id,answer_id,split,claim_text,citation_id,origin,planted_type,"
    "label,evidence_quote,notes\n"
)


def _sheet(tmp_path, labels):
    rows = [HEADER]
    for i, lab in enumerate(labels):
        rows.append(f"q01-c{i:02d},q01,dev,claim {i},S1,organic,,{lab},,\n")
    rows.append("q01-p01,q01,dev,planted one,S1,planted,contradiction,Contradicted,,\n")
    path = tmp_path / "labels.csv"
    path.write_text("".join(rows), encoding="utf-8")
    return path


def test_pick_sample_is_seeded_and_keeps_sheet_order():
    ids = [f"c{i}" for i in range(30)]
    a = pick_sample(ids, 5, seed=1)
    assert a == pick_sample(ids, 5, seed=1)
    assert a == sorted(a, key=ids.index)
    assert a != pick_sample(ids, 5, seed=2)


def test_pick_sample_rejects_too_many():
    with pytest.raises(ValueError):
        pick_sample(["a"], 2, seed=0)


def test_blind_sample_hides_labels_skips_planted_and_refuses_overwrite(tmp_path):
    sheet = _sheet(tmp_path, ["Supported"] * 6 + ["NOT_MENTIONED"] * 2)
    out = tmp_path / "blind.csv"
    ids = write_blind_sample(sheet, out, n=4, seed=3)
    text = out.read_text(encoding="utf-8")
    assert "Supported" not in text and "NOT_MENTIONED" not in text and "q01-p01" not in text
    rows = list(csv.DictReader(text.splitlines()))
    assert [r["claim_id"] for r in rows] == ids and all(r["label"] == "" for r in rows)
    with pytest.raises(FileExistsError):
        write_blind_sample(sheet, out, n=4, seed=3)


def test_compare_reports_agreement_kappa_and_flips(tmp_path):
    sheet = _sheet(tmp_path, ["Supported", "Supported", "NOT_MENTIONED", "Contradicted"])
    pass2 = tmp_path / "p2.csv"
    pass2.write_text(
        "claim_id,answer_id,claim_text,citation_id,label,evidence_quote\n"
        "q01-c00,q01,x,S1,Supported,\nq01-c01,q01,x,S1,not mentioned,\n"
        "q01-c02,q01,x,S1,NOT_MENTIONED,\nq01-c03,q01,x,S1,Contradicted,\n",
        encoding="utf-8",
    )
    r = compare(sheet, pass2)
    assert r["n"] == 4 and r["agreement"] == 0.75
    assert r["disagreements"] == [("q01-c01", "SUPPORTED", "NOT_MENTIONED")]
    assert r["flag_agreement"] == 0.75 and 0 < r["kappa_4class"] < 1


def test_compare_rejects_blank_labels(tmp_path):
    sheet = _sheet(tmp_path, ["Supported"])
    pass2 = tmp_path / "p2.csv"
    pass2.write_text(
        "claim_id,answer_id,claim_text,citation_id,label,evidence_quote\nq01-c00,q01,x,S1,,\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not relabeled"):
        compare(sheet, pass2)
