# claimcheck

A tool that checks every claim in an AI answer against its cited source and flags unsupported ones.

> Status: work in progress. Results table, architecture diagram, and quick start are added as the
> project is built.

## Labels

| Label | Meaning |
|---|---|
| `SUPPORTED` | The cited source states the claim (paraphrase allowed). |
| `CONTRADICTED` | The cited source states something incompatible with the claim. |
| `NOT_MENTIONED` | The cited source neither supports nor contradicts the claim. |
| `CITATION_MISSING` | The answer cites a source that was not provided. |

"Flagged" means any label other than `SUPPORTED`. Precision, recall, and F1 are reported for the
flagged class.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
```

Unit tests mock all LLM (large language model) calls, so they are free and deterministic.
