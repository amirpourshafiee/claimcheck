"""Stage 4: render a Report as JSON and as readable markdown."""

from __future__ import annotations

import json

from claimcheck.schema import Report


def to_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)


def _cell(text: str) -> str:
    """Make text safe for a markdown table cell."""
    return " ".join(text.split()).replace("|", "\\|")


def to_markdown(report: Report) -> str:
    claims = {c.claim_id: c for c in report.claims}
    counts = report.summary()
    flagged = report.flagged()
    lines = [
        f"# Claim check report: {report.answer_id}",
        "",
        f"{len(flagged)} of {len(report.verdicts)} checked claims were flagged.",
        "",
        "| Label | Count |",
        "|---|---|",
        *[f"| {label} | {n} |" for label, n in counts.items()],
        "",
    ]
    if flagged:
        lines += ["## Flagged claims", "", "| Claim | Cited | Verdict | Why |", "|---|---|---|---|"]
        for v in flagged:
            c = claims[v.claim_id]
            lines.append(
                f"| {_cell(c.text)} | {c.citation_id or ''} | {v.label.value} | "
                f"{_cell(v.rationale)} |"
            )
        lines.append("")
    supported = [v for v in report.verdicts if not v.label.is_flagged]
    if supported:
        lines += ["## Supported claims", ""]
        lines += [f"- {_cell(claims[v.claim_id].text)}" for v in supported]
        lines.append("")
    if report.uncited:
        lines += ["## Not evaluated (no citation)", ""]
        lines += [f"- {_cell(claims[cid].text)}" for cid in report.uncited]
        lines.append("")
    return "\n".join(lines)
