# claimcheck

A tool that checks every claim in an AI answer against its cited source and flags unsupported ones.

> Status: pipeline, labeled dataset and evaluation are done. See [Results](#results) for what the
> numbers do and do not show.

## How it works

```mermaid
flowchart LR
    A[AI answer with<br/>citations like S1] --> B[1. Split into<br/>atomic claims<br/>LLM, extract.py]
    B --> C[2. Match claim to<br/>cited source<br/>no LLM, match.py]
    S[(Provided sources<br/>S1, S2, ...)] --> C
    C -->|source not provided| X[CITATION_MISSING]
    C -->|source found| D[3. Judge claim vs source<br/>LLM, judge.py]
    D --> V{SUPPORTED<br/>CONTRADICTED<br/>NOT_MENTIONED}
    X --> R[4. Report<br/>JSON + markdown<br/>report.py]
    V --> R
```

1. **Split.** An LLM (large language model) turns the answer into one-fact claims and keeps each
   claim's citation marker.
2. **Match.** Plain code looks up the cited source. A citation to a source that was not provided is
   `CITATION_MISSING`, decided without any model call.
3. **Judge.** An LLM reads only the cited excerpt and returns `SUPPORTED`, `CONTRADICTED`, or
   `NOT_MENTIONED` with a quote. The quote is checked against the excerpt, and a quote that is not
   in it is discarded, so the judge cannot invent evidence. The source is fenced as data so text
   inside it cannot give the judge instructions.
4. **Report.** JSON for programs, markdown for people. "Flagged" means any label except `SUPPORTED`.

| Label | Meaning |
|---|---|
| `SUPPORTED` | The cited source states the claim (paraphrase allowed). |
| `CONTRADICTED` | The cited source states something incompatible with the claim. |
| `NOT_MENTIONED` | The cited source neither supports nor contradicts the claim. |
| `CITATION_MISSING` | The answer cites a source that was not provided. |

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Try the pipeline with no API key (scripted stand-ins for the two LLM calls):

```python
import json
from claimcheck.judge import LLMJudge
from claimcheck.llm import ScriptedClient
from claimcheck.pipeline import run_pipeline
from claimcheck.report import to_markdown

answer = "The device was found in 1901. [S1] It has 99 gears. [S2]"
sources = {"S1": "The device was discovered in 1901 in a shipwreck."}

extract = ScriptedClient(
    [
        json.dumps(
            [
                {"text": "The device was found in 1901.", "citation": "S1"},
                {"text": "The device has 99 gears.", "citation": "S2"},
            ]
        )
    ]
)
judge = LLMJudge(
    ScriptedClient(
        [
            json.dumps(
                {
                    "label": "SUPPORTED",
                    "evidence_quote": "discovered in 1901",
                    "rationale": "same year",
                }
            )
        ]
    )
)
print(to_markdown(run_pipeline("demo", answer, sources, extract, judge)))
```

For real calls, install the extra (`pip install -e ".[llm]"`), copy `.env.example` to `.env`, set
`ANTHROPIC_API_KEY`, and wrap `AnthropicClient()` in `CachedClient(client, "claude-haiku-5-5")`
(caches replies and enforces a hard cap on paid calls) in place of each `ScriptedClient`.

## Evaluate a judge

```bash
python -m claimcheck.evaluate --judge baseline --split dev      # free word-overlap baseline
python -m claimcheck.evaluate --judge llm --split dev --yes     # about $0.01, prints estimate first
```

Paid runs print a cost estimate and need `--yes`. The test split is blocked unless `--final` is
passed, so it can only be used once the prompt and settings are frozen. Each run writes
`results/<judge>_<split>.json`, `.md`, and a per-claim `_predictions.csv`.

## Dataset

113 hand-labeled claims from AI answers about 12 questions, each citing two Wikipedia excerpts
(700 words each): 72 organic claims and 41 planted failures. Read [DATASHEET.md](DATASHEET.md)
before trusting any number, and [eval/LABELING_GUIDE.md](eval/LABELING_GUIDE.md) for the rules.
Excerpts are Wikipedia text under CC BY-SA 4.0 (see each file's header).

The answers in `eval/answers/` were written with Grok (xAI) and are AI-generated; see
[eval/answers/README.md](eval/answers/README.md) and the datasheet for the terms I checked.

A finding that needs no judge: the answer-writing chatbot got **13 of 72 organic claims (18%)**
wrong or unsupported by the cited excerpt, 5 of them outright contradictions.

## Results

Held-out test split (76 claims, 8 answers), run once with everything frozen. Full report with
error analysis: [EVALUATION.md](EVALUATION.md).

| Judge | Slice | n | Precision | Recall | F1 for flagged (95% CI) |
|---|---|---|---|---|---|
| Claude Haiku 5.5 | organic | 48 | 0.89 | 0.89 | **0.89** (0.67 to 1.00) |
| Word-overlap baseline | organic | 48 | 0.70 | 0.78 | 0.74 (0.50 to 0.94) |
| Claude Haiku 5.5 | all, judge only | 69 | 0.97 | 0.97 | 0.97 (0.92 to 1.00) |
| Word-overlap baseline | all, judge only | 69 | 0.90 | 0.90 | 0.90 (0.81 to 0.97) |

Read these carefully:
- The organic row is the one that matters. It rests on **9 flagged claims**, so the interval is
  wide. The paired F1 gain over the baseline is +0.15 (95% CI 0.00 to +0.31): suggestive, not
  established.
- Planted claims are easy (the baseline scores 0.98 on them), so the combined row is flattered.
- All four judge errors are organic and look like borderline or wrong labels (EVALUATION.md). The
  labels were not changed after seeing test output.
- Cost of the test run: $0.020 for 69 calls.

## Limitations

Small dataset, one annotator, one answer-writing model, truncated excerpts ("not mentioned"
means "not in the excerpt"), and Wikipedia text the judge may have memorized. Details are in
[DATASHEET.md](DATASHEET.md).

## Development

```bash
ruff check .
pytest
```

Unit tests mock every LLM call, so they are free and deterministic. CI (continuous
integration) runs lint and tests on Python 3.10 and 3.12.

## License

Code: MIT. Dataset text derived from Wikipedia: CC BY-SA 4.0.
