"""Build and validate the hand-labeling spreadsheet (eval/dataset/labels.csv).

Workflow: paste the claim-splitting output into claims_raw.csv, run `build` once to create the
labeling sheet, label it in any spreadsheet app, then run `validate` as often as you like.
`build` refuses to overwrite an existing sheet so labels can never be lost by accident.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from claimcheck.schema import Label
from claimcheck.wikisource import load_topics

RAW_COLUMNS = ["claim_id", "answer_id", "claim_text", "citation_id"]
COLUMNS = [
    "claim_id",
    "answer_id",
    "split",
    "claim_text",
    "citation_id",
    "origin",
    "planted_type",
    "label",
    "evidence_quote",
    "notes",
]
ORIGINS = {"organic", "planted"}
PLANTED_TYPES = {"contradiction", "unsupported_addition", "wrong_source", "fake_citation"}
MAX_QUOTE_WORDS = 15
# Each source id in the topics file must account for at least this share of organic claims.
MIN_CITATION_SHARE = 0.30


def _read_csv(path: Path) -> list[dict]:
    # utf-8-sig strips the byte-order mark that Excel and Numbers sometimes add.
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build_sheet(raw_path: Path, topics_path: Path, out_path: Path) -> int:
    """Create the labeling sheet from raw claims. Returns the number of rows written."""
    if out_path.exists():
        raise FileExistsError(f"{out_path} already exists; refusing to overwrite labels")
    rows = _read_csv(raw_path)
    if not rows:
        raise ValueError(f"{raw_path} has no rows")
    missing = [c for c in RAW_COLUMNS if c not in rows[0]]
    if missing:
        raise ValueError(f"{raw_path} is missing columns: {missing}")
    split_of = {t["answer_id"]: t["split"] for t in load_topics(topics_path)}
    out_rows = []
    for r in rows:
        answer_id = r["answer_id"].strip()
        if answer_id not in split_of:
            raise ValueError(f"unknown answer_id {answer_id!r} (not in topics file)")
        out_rows.append(
            {
                "claim_id": r["claim_id"].strip(),
                "answer_id": answer_id,
                "split": split_of[answer_id],
                "claim_text": r["claim_text"].strip(),
                "citation_id": r["citation_id"].strip(),
                "origin": "organic",
                "planted_type": "",
                "label": "",
                "evidence_quote": "",
                "notes": "",
            }
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(out_rows)
    return len(out_rows)


def validate_sheet(
    sheet_path: Path, sources_dir: Path, topics_path: Path
) -> tuple[list[str], dict]:
    """Check the sheet for mistakes. Returns (problems, stats). Empty problems means clean."""
    rows = _read_csv(sheet_path)
    topics = load_topics(topics_path)
    split_of = {t["answer_id"]: t["split"] for t in topics}
    source_ids = sorted({s["source_id"] for t in topics for s in t["sources"]})
    problems: list[str] = []
    warnings: list[str] = []  # worth knowing, but they do not affect any metric
    seen: set[str] = set()
    labels: Counter = Counter()
    for i, r in enumerate(rows, start=2):  # row 1 is the header
        where = f"row {i} ({r.get('claim_id', '?')})"
        if r.get("claim_id") in seen:
            problems.append(f"{where}: duplicate claim_id")
        seen.add(r.get("claim_id", ""))
        if r.get("answer_id") not in split_of:
            problems.append(f"{where}: unknown answer_id {r.get('answer_id')!r}")
        elif r.get("split") != split_of[r["answer_id"]]:
            problems.append(f"{where}: split {r.get('split')!r} != topics file (run fix-splits)")
        if r.get("origin") not in ORIGINS:
            problems.append(f"{where}: origin must be one of {sorted(ORIGINS)}")
        if r.get("origin") == "planted" and r.get("planted_type") not in PLANTED_TYPES:
            problems.append(f"{where}: planted rows need planted_type in {sorted(PLANTED_TYPES)}")
        if r.get("origin") == "organic" and r.get("planted_type"):
            problems.append(f"{where}: organic rows must not have planted_type")
        raw_label = (r.get("label") or "").strip()
        if not raw_label:
            labels["UNLABELED"] += 1
            continue
        try:
            label = Label.parse(raw_label)
        except ValueError:
            problems.append(f"{where}: invalid label {raw_label!r}")
            continue
        labels[label.value] += 1
        source_exists = (sources_dir / f"{r['answer_id']}_{r['citation_id']}.txt").exists()
        if label is Label.CITATION_MISSING and source_exists:
            problems.append(f"{where}: CITATION_MISSING but source {r['citation_id']} exists")
        if label is not Label.CITATION_MISSING and not source_exists:
            problems.append(
                f"{where}: cites {r['citation_id']!r} (no such source) but is not CITATION_MISSING"
            )
        if len((r.get("evidence_quote") or "").split()) > MAX_QUOTE_WORDS:
            warnings.append(f"{where}: evidence_quote longer than {MAX_QUOTE_WORDS} words")
    organic = [r for r in rows if r.get("origin") == "organic"]
    by_citation = Counter(r.get("citation_id") for r in organic)
    for sid in source_ids:
        if organic and by_citation[sid] / len(organic) < MIN_CITATION_SHARE:
            problems.append(
                f"citation imbalance: {sid} has {by_citation[sid]} of {len(organic)} organic "
                f"claims; each source needs at least {MIN_CITATION_SHARE:.0%} so every source "
                "is actually tested"
            )
    stats = {
        "rows": len(rows),
        "by_citation_organic": dict(by_citation),
        "warnings": warnings,
        "by_label": dict(labels),
        "by_split": dict(Counter(r.get("split") for r in rows)),
        "by_origin": dict(Counter(r.get("origin") for r in rows)),
        "unsure": sum("UNSURE" in (r.get("notes") or "").upper() for r in rows),
    }
    return problems, stats


def fix_splits(sheet_path: Path, topics_path: Path) -> list[tuple[str, str, str]]:
    """Rewrite each row's split from topics.json. Returns (claim_id, old, new) for every change.

    The rule is fixed by the labeling guide: a row, planted or organic, inherits the split of its
    answer. Only the split column is touched. The write is atomic (temp file, then rename).
    """
    split_of = {t["answer_id"]: t["split"] for t in load_topics(topics_path)}
    rows = _read_csv(sheet_path)
    changes = []
    for r in rows:
        if r["answer_id"] not in split_of:
            raise ValueError(f"{r['claim_id']}: unknown answer_id {r['answer_id']!r}")
        new = split_of[r["answer_id"]]
        if r["split"] != new:
            changes.append((r["claim_id"], r["split"], new))
            r["split"] = new
    if changes:
        tmp = sheet_path.with_suffix(".csv.tmp")
        with tmp.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows({c: r.get(c, "") for c in COLUMNS} for r in rows)
        tmp.replace(sheet_path)
    return changes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="create labels.csv from claims_raw.csv (once)")
    b.add_argument("--raw", type=Path, default=Path("eval/dataset/claims_raw.csv"))
    b.add_argument("--topics", type=Path, default=Path("eval/topics.json"))
    b.add_argument("--out", type=Path, default=Path("eval/dataset/labels.csv"))
    v = sub.add_parser("validate", help="check labels.csv for mistakes and print counts")
    v.add_argument("--sheet", type=Path, default=Path("eval/dataset/labels.csv"))
    v.add_argument("--sources", type=Path, default=Path("eval/sources"))
    v.add_argument("--topics", type=Path, default=Path("eval/topics.json"))
    f = sub.add_parser("fix-splits", help="set every row's split from topics.json")
    f.add_argument("--sheet", type=Path, default=Path("eval/dataset/labels.csv"))
    f.add_argument("--topics", type=Path, default=Path("eval/topics.json"))
    args = ap.parse_args(argv)
    if args.cmd == "fix-splits":
        changes = fix_splits(args.sheet, args.topics)
        for cid, old, new in changes:
            print(f"{cid}: {old} -> {new}")
        print(f"{len(changes)} row(s) changed")
        return 0
    if args.cmd == "build":
        n = build_sheet(args.raw, args.topics, args.out)
        print(f"Wrote {n} rows to {args.out}")
        return 0
    problems, stats = validate_sheet(args.sheet, args.sources, args.topics)
    for p in problems:
        print("PROBLEM:", p)
    for w in stats["warnings"]:
        print("WARNING:", w)
    print("STATS:", {k: v for k, v in stats.items() if k != "warnings"})
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
