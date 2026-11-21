"""Intra-annotator consistency check: relabel a random sample blind, then compare.

Why: the hand labels are the ground truth for every metric, so their own reliability caps how
much any judge score can mean. Relabeling 20 random organic claims at least 24 hours later, with
the original labels hidden, measures how often the same person disagrees with themselves.

    python -m claimcheck.consistency sample --out ~/Downloads/relabel_blind.csv
    python -m claimcheck.consistency compare --pass2 ~/Downloads/relabel_blind.csv
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

from claimcheck.dataset import load_examples
from claimcheck.metrics import cohen_kappa
from claimcheck.schema import Label

BLIND_COLUMNS = ["claim_id", "answer_id", "claim_text", "citation_id", "label", "evidence_quote"]
DEFAULT_SEED = 20261121


def pick_sample(claim_ids: list[str], n: int, seed: int) -> list[str]:
    """A seeded random sample, returned in sheet order so row order leaks nothing."""
    if n > len(claim_ids):
        raise ValueError(f"asked for {n} claims but only {len(claim_ids)} are eligible")
    chosen = set(random.Random(seed).sample(sorted(claim_ids), n))
    return [c for c in claim_ids if c in chosen]


def write_blind_sample(sheet: Path, out: Path, n: int = 20, seed: int = DEFAULT_SEED) -> list[str]:
    """Write the claims to relabel. Gold labels are NOT written. Refuses to overwrite."""
    if Path(out).exists():
        raise FileExistsError(f"{out} already exists; refusing to overwrite")
    organic = [e for e in load_examples(sheet) if e.origin == "organic"]
    ids = pick_sample([e.claim.claim_id for e in organic], n, seed)
    by_id = {e.claim.claim_id: e for e in organic}
    with Path(out).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(BLIND_COLUMNS)
        for cid in ids:
            e = by_id[cid]
            w.writerow([cid, e.answer_id, e.claim.text, e.claim.citation_id, "", ""])
    return ids


def compare(sheet: Path, pass2: Path) -> dict:
    """Agreement between the original labels and the blind second pass."""
    gold = {e.claim.claim_id: e.gold for e in load_examples(sheet)}
    with Path(pass2).open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    first, second, flips = [], [], []
    for r in rows:
        raw = (r.get("label") or "").strip()
        if not raw:
            raise ValueError(f"{r['claim_id']} was not relabeled")
        cid = r["claim_id"].strip()
        if cid not in gold:
            raise ValueError(f"unknown claim_id {cid}")
        new = Label.parse(raw)
        first.append(gold[cid])
        second.append(new)
        if new != gold[cid]:
            flips.append((cid, gold[cid].value, new.value))
    flag = [g.is_flagged for g in first], [s.is_flagged for s in second]
    return {
        "n": len(first),
        "agreement": sum(a == b for a, b in zip(first, second, strict=True)) / len(first),
        "kappa_4class": cohen_kappa(first, second),
        "flag_agreement": sum(a == b for a, b in zip(*flag, strict=True)) / len(first),
        "disagreements": flips,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample", help="write the blind relabel sheet")
    s.add_argument("--sheet", type=Path, default=Path("eval/dataset/labels.csv"))
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--n", type=int, default=20)
    s.add_argument("--seed", type=int, default=DEFAULT_SEED)
    c = sub.add_parser("compare", help="compare the second pass with the original labels")
    c.add_argument("--sheet", type=Path, default=Path("eval/dataset/labels.csv"))
    c.add_argument("--pass2", type=Path, required=True)
    args = ap.parse_args(argv)
    if args.cmd == "sample":
        ids = write_blind_sample(args.sheet, args.out, args.n, args.seed)
        print(f"Wrote {len(ids)} claims to {args.out}. Relabel at least 24 hours after you")
        print("finished the original labels, from the source excerpts, without opening labels.csv.")
        return 0
    r = compare(args.sheet, args.pass2)
    print(
        f"n={r['n']}  agreement={r['agreement']:.0%}  kappa(4-class)={r['kappa_4class']:.2f}  "
        f"flagged-vs-not agreement={r['flag_agreement']:.0%}"
    )
    for cid, a, b in r["disagreements"]:
        print(f"  {cid}: first={a} second={b}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
