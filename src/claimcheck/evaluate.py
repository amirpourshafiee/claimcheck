"""Run a judge over the labeled dataset and report honest metrics.

Two views are reported side by side, because they answer different questions:
- end_to_end: every claim, including planted fake citations. match.py catches those with a
  plain lookup, so they are free true positives for the whole pipeline.
- judge_only: drops the rows whose gold label is CITATION_MISSING, so the judge is scored on the
  claims it actually has to decide. Quote this one when talking about the judge.

Slices (all, organic, planted) are reported separately, never only pooled: planted claims make
flagged claims far more common than in real answers, which inflates pooled precision.

The test split is reserved. Running it requires --final, so it cannot be used by accident while
prompts and thresholds are still being tuned on dev.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from claimcheck.baseline import LexicalBaseline
from claimcheck.dataset import Example, load_examples, load_sources
from claimcheck.judge import JUDGE_ERROR_PREFIX, Judge, JudgeError
from claimcheck.metrics import bootstrap_ci, cohen_kappa, confusion_matrix, flagged_prf
from claimcheck.pipeline import check_claims
from claimcheck.schema import Label, Verdict


def run_judge(
    examples: Sequence[Example], sources: dict[str, dict[str, str]], judge: Judge
) -> dict[str, Verdict]:
    """Run stages 2 and 3 on the gold claims. Returns claim_id -> Verdict."""
    by_answer: dict[str, list] = defaultdict(list)
    for ex in examples:
        if ex.claim.citation_id is None:
            raise ValueError(f"{ex.claim.claim_id}: uncited claims are not supported in evaluation")
        by_answer[ex.answer_id].append(ex.claim)
    verdicts: dict[str, Verdict] = {}
    for answer_id, claims in by_answer.items():
        for claim in claims:
            try:
                report = check_claims(answer_id, [claim], sources.get(answer_id, {}), judge)
            except JudgeError as e:
                # One unparseable reply must not abort a paid run. It is scored as SUPPORTED
                # (not flagged), which can only hurt the judge's recall, and it is counted.
                verdicts[claim.claim_id] = Verdict(
                    claim.claim_id,
                    Label.SUPPORTED,
                    rationale=f"{JUDGE_ERROR_PREFIX} {e}",
                    judge=getattr(judge, "name", ""),
                )
                continue
            verdicts.update({v.claim_id: v for v in report.verdicts})
    return verdicts


# Resampling whole answers needs enough answers to draw from. With fewer, the interval collapses
# to a single value and falsely suggests certainty, so it is reported as unavailable instead.
MIN_GROUPS_FOR_CI = 5


def _slice(name: str, items: list[tuple[Example, Label]], n_resamples: int, seed: int) -> dict:
    y_true = [ex.gold for ex, _ in items]
    y_pred = [pred for _, pred in items]
    groups = [ex.answer_id for ex, _ in items]
    prf = flagged_prf(y_true, y_pred)
    n_flagged = prf.tp + prf.fn
    ci = None
    if n_flagged and len(set(groups)) >= MIN_GROUPS_FOR_CI:
        ci = bootstrap_ci(
            y_true, y_pred, lambda t, p: flagged_prf(t, p).f1, groups, n_resamples, seed
        )
    return {
        "slice": name,
        "n": len(items),
        "gold_flagged": n_flagged,
        "prevalence": n_flagged / len(items),
        "precision": prf.precision,
        "recall": prf.recall,
        "f1": prf.f1,
        "f1_ci95": list(ci) if ci else None,
        "kappa_4class": cohen_kappa(y_true, y_pred),
        "tp": prf.tp,
        "fp": prf.fp,
        "fn": prf.fn,
        "tn": prf.tn,
    }


def evaluate(
    examples: Sequence[Example],
    verdicts: dict[str, Verdict],
    n_resamples: int = 2000,
    seed: int = 0,
) -> dict:
    """Compute metrics for both views and every slice. Every example must have a gold label."""
    if any(ex.gold is None for ex in examples):
        raise ValueError("every example needs a gold label")
    rows = [(ex, verdicts[ex.claim.claim_id].label) for ex in examples]
    gold_missing = [(ex, p) for ex, p in rows if ex.gold is Label.CITATION_MISSING]
    views = {"end_to_end": rows, "judge_only": [r for r in rows if r not in gold_missing]}
    out: dict = {
        "judge_errors": sorted(
            cid for cid, v in verdicts.items() if v.rationale.startswith(JUDGE_ERROR_PREFIX)
        ),
        "views": {},
        "matcher_check": {
            "gold_citation_missing": len(gold_missing),
            "caught": sum(p is Label.CITATION_MISSING for _, p in gold_missing),
            "false_alarms": sum(
                p is Label.CITATION_MISSING
                for ex, p in rows
                if ex.gold is not Label.CITATION_MISSING
            ),
        },
    }
    for view_name, view_rows in views.items():
        slices = {
            "all": view_rows,
            "organic": [r for r in view_rows if r[0].origin == "organic"],
            "planted": [r for r in view_rows if r[0].origin == "planted"],
        }
        out["views"][view_name] = {
            "slices": [_slice(n, r, n_resamples, seed) for n, r in slices.items() if r],
            "confusion_matrix": confusion_matrix(
                [ex.gold for ex, _ in view_rows], [p for _, p in view_rows]
            ),
        }
    return out


def to_markdown(results: dict, title: str) -> str:
    lines = [f"# {title}", ""]
    for view, data in results["views"].items():
        lines += [
            f"## {view}",
            "",
            "| slice | n | flagged | precision | recall | F1 (95% CI) | kappa (4-class) |",
            "|---|---|---|---|---|---|---|",
        ]
        for s in data["slices"]:
            ci = f"[{s['f1_ci95'][0]:.2f}, {s['f1_ci95'][1]:.2f}]" if s["f1_ci95"] else "(CI n/a)"
            lines.append(
                f"| {s['slice']} | {s['n']} | {s['gold_flagged']} ({s['prevalence']:.0%}) | "
                f"{s['precision']:.2f} | {s['recall']:.2f} | {s['f1']:.2f} {ci} | "
                f"{s['kappa_4class']:.2f} |"
            )
        lines.append("")
    m = results["matcher_check"]
    lines.append(
        f"Citation matcher: caught {m['caught']} of {m['gold_citation_missing']} missing "
        f"citations, {m['false_alarms']} false alarms."
    )
    if results.get("judge_errors"):
        lines.append(
            f"Judge errors (unparseable reply, scored as not flagged): "
            f"{len(results['judge_errors'])}: {', '.join(results['judge_errors'])}."
        )
    return "\n".join(lines) + "\n"


def check_run_allowed(split: str, final: bool, judge_kind: str, confirmed: bool) -> str | None:
    """Return an error message if this run must not start, else None."""
    if split in ("test", "all") and not final:
        return (
            "the test split is reserved for the final run. Pass --final only once prompts and "
            "thresholds are frozen."
        )
    if judge_kind == "llm" and not confirmed:
        return "this run spends money. Review the cost estimate above, then add --yes."
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate a judge on the labeled dataset.")
    ap.add_argument("--judge", choices=["baseline", "llm"], required=True)
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    ap.add_argument("--threshold", type=float, default=0.7, help="baseline word-overlap cutoff")
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--max-calls", type=int, default=150, help="hard cap on paid API calls")
    ap.add_argument("--final", action="store_true", help="allow the reserved test split")
    ap.add_argument("--yes", action="store_true", help="confirm a run that spends money")
    ap.add_argument("--sheet", type=Path, default=Path("eval/dataset/labels.csv"))
    ap.add_argument("--sources", type=Path, default=Path("eval/sources"))
    ap.add_argument("--out-dir", type=Path, default=Path("results"))
    args = ap.parse_args(argv)

    examples = load_examples(args.sheet, split=None if args.split == "all" else args.split)
    sources = load_sources(args.sources)

    if args.judge == "llm":
        from claimcheck.cost import HAIKU_5_5, SONNET_5_5, estimate_judge_run

        pricing = SONNET_5_5 if "sonnet" in args.model else HAIKU_5_5
        est = estimate_judge_run(examples, sources, pricing)
        print(
            f"Estimate ({pricing.model} prices): {est.calls} calls, "
            f"expected ${est.expected_usd:.3f}, worst case ${est.worst_case_usd:.3f}. "
            f"Call cap: {args.max_calls}."
        )
    error = check_run_allowed(args.split, args.final, args.judge, args.yes)
    if error:
        print(f"refusing to run: {error}", file=sys.stderr)
        return 2

    meta: dict = {"split": args.split, "date": date.today().isoformat(), "n": len(examples)}
    if args.judge == "baseline":
        judge: Judge = LexicalBaseline(threshold=args.threshold)
        meta["threshold"] = args.threshold
    else:
        from claimcheck.anthropic_client import AnthropicClient
        from claimcheck.judge import PROMPT_VERSION, LLMJudge
        from claimcheck.llm import CachedClient

        real = AnthropicClient(model=args.model)
        cached = CachedClient(real, args.model, max_calls=args.max_calls)
        judge = LLMJudge(cached, name=f"llm-judge-{args.model}-{PROMPT_VERSION}")
        meta["model"] = args.model
    verdicts = run_judge(examples, sources, judge)
    if args.judge == "llm":
        meta.update(
            real_calls=cached.calls_made,
            cache_hits=cached.cache_hits,
            measured_usd=round(real.spent_usd(pricing), 6),
            thinking_tokens=real.thinking_tokens,
        )
    results = evaluate(examples, verdicts)
    results["meta"] = {"judge": judge.name, **meta}

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{judge.name}_{args.split}"
    (args.out_dir / f"{stem}.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    md = to_markdown(results, f"{judge.name} on {args.split} ({len(examples)} claims)")
    (args.out_dir / f"{stem}.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
