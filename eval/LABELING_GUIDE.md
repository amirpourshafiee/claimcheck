# Labeling guide

You are the ground truth for this project, so consistency matters more than speed. Read this whole
file once before you label anything. Budget: about 3 to 4 hours for roughly 90 claims.

## Workflow

1. **Generate answers.** Paste `prompts/01_generate_answers.md` into a fresh chat. Save the reply
   to `eval/answers/answers_raw.md`. Record the chatbot, model name, and date.
2. **Split into claims.** In the same chat, paste `prompts/02_split_claims.md`. Save the CSV block
   as `eval/dataset/claims_raw.csv`. Then check the split: each claim is one fact, stands alone,
   and keeps the right citation. Fix mistakes by editing the CSV text. Do NOT drop or add claims
   based on whether they look easy or hard.
   The cap is per citation (3 per source per answer), so both sources are tested. `validate`
   fails if either source has under 30% of the organic claims.
3. **Build the sheet (once).** `python -m claimcheck.labelsheet build` creates
   `eval/dataset/labels.csv`. It refuses to overwrite an existing sheet, so labels are safe.
4. **Label organic claims.** Open `labels.csv` in Numbers or Google Sheets. For each row, read the
   claim, open `eval/sources/<answer_id>_<citation_id>.txt` (for example `q01_S1.txt`), and fill
   `label`, plus `evidence_quote` when you have one. Use ONLY that file.
5. **Plant claims.** Only after ALL organic rows are labeled, add planted rows (recipes below).
6. **Validate.** `python -m claimcheck.labelsheet validate` catches typos and rule violations
   and prints label counts. Run it often.
7. **Relabel a sample 24 or more hours later** (see "Consistency check").

Do not run any model on these claims while labeling, and do not look at model output first. Your
labels must not be anchored by a judge.

## The four labels

| Label | Use when |
|---|---|
| `SUPPORTED` | The cited excerpt states the claim. Paraphrase and unit conversion are fine. |
| `CONTRADICTED` | The cited excerpt states something incompatible with the claim. |
| `NOT_MENTIONED` | The cited excerpt neither supports nor contradicts the claim. |
| `CITATION_MISSING` | The cited source id has no excerpt file (planted rows only). |

"Flagged" (the positive class for precision and recall) means any label except `SUPPORTED`.

## Decision rules for hard cases

1. **Ignore what you know.** If the excerpt does not say it, the label is not `SUPPORTED`, even if
   you know it is true. The tool can only see the excerpt.
2. **Silent versus different.** If the excerpt gives a different specific answer to the same
   question, it is `CONTRADICTED`. If it is simply silent, it is `NOT_MENTIONED`.
3. **Partly supported.** If one part is supported and another part is not, label
   `NOT_MENTIONED`. If any part is contradicted, label `CONTRADICTED`. Write `SPLIT` in `notes`:
   a mixed claim means the split was not atomic.
4. **Inference.** `SUPPORTED` only if a careful reader gets there in one obvious step from the
   excerpt with no outside knowledge (for example arithmetic on stated numbers). Otherwise
   `NOT_MENTIONED`.
5. **Numbers and dates.** Equal up to rounding the excerpt itself would accept ("about",
   unit conversion) is `SUPPORTED`. A different number or date is `CONTRADICTED`. A value inside
   a stated range is `SUPPORTED`.
6. **Hedging.** If the excerpt says "may", "is believed", or "there is speculation" and the claim
   states it as fact, label `NOT_MENTIONED`, unless the excerpt states the opposite.
7. **Wrong source.** If the fact appears in the OTHER excerpt but not the cited one, label
   `NOT_MENTIONED` and write `IN OTHER SOURCE` in `notes`. This is the realistic
   misattribution case.
8. **`CITATION_MISSING`** is only for ids with no excerpt file (for example S3). Never use it
   for anything else.
9. **Unsure.** Spend at most 2 minutes per claim. Pick your best label and write `UNSURE` in
   `notes`. The count of unsure rows goes into the datasheet.

## Worked examples (Antikythera mechanism excerpt, `q01_S1.txt`)

| Claim | Label | Why |
|---|---|---|
| "The mechanism was recovered from a shipwreck off the Greek island of Antikythera in 1901." | `SUPPORTED` | Stated directly. |
| "X-ray scans showed the mechanism had 37 meshing bronze gears." | `CONTRADICTED` | Excerpt says 35. |
| "The mechanism is on display at the Louvre." | `CONTRADICTED` | Excerpt names the National Archaeological Museum. |
| "The mechanism's case was made of cedar wood." | `NOT_MENTIONED` | Excerpt says wooden-framed, not which wood. |
| "The mechanism calculated the positions of the five classical planets." | `NOT_MENTIONED` | Excerpt only reports speculation (rule 6). |

Check these against the file yourself. Treat the table as practice, not as a substitute for
reading the excerpt.

## Planting claims

Goal: about 24 planted rows, roughly 6 of each type, so the test set has known failure modes.
Add them as new rows. Use `origin` = `planted`, a `planted_type`, and ids like `q01-p01`. Give each
planted row the `answer_id` of the answer it was derived from, so it inherits that answer's
dev/test split. Spread them across answers and across the dev and test splits.

| `planted_type` | Recipe | Expected label |
|---|---|---|
| `contradiction` | Copy a `SUPPORTED` organic claim and change one checkable detail (number, date, name, direction, or comparison). The change must be detectable from the excerpt. | `CONTRADICTED` |
| `unsupported_addition` | Write a plausible, specific claim about the topic that is NOT in the cited excerpt. Confirm by searching the file text. It may be true in the real world. That is realistic. | `NOT_MENTIONED` |
| `wrong_source` | Copy a `SUPPORTED` claim from S1 and cite S2 (or the reverse), only when the other excerpt does not state it. | `NOT_MENTIONED` |
| `fake_citation` | Copy any claim and cite `S3`, which does not exist. | `CITATION_MISSING` |

Anti-leak rules: write planted claims in the same plain style as the organic ones, avoid odd
phrasing that gives the plant away, and do not always place them last in an answer. Still read
the excerpt for every planted row: if the source forces a different label than the one you
intended, trust the source and say so in `notes`.

## Generator bias

If the same model family writes the answers and later judges them, it may be biased toward its
own claims. Preferred fix: generate answers with a chatbot from a different company than the
judge. If you cannot, say so plainly in the datasheet's limitations. Either way, record which
model wrote the answers.

## Consistency check

At least 24 hours after you finish, relabel 20 random organic rows from scratch with their labels
hidden. `python -m claimcheck.consistency sample --out relabel_blind.csv` writes the sheet (seeded,
no labels in it), and `python -m claimcheck.consistency compare --pass2 relabel_blind.csv` reports
agreement and Cohen's kappa. The agreement between your two passes is the ceiling for any judge: no judge can sensibly agree with you more than you
agree with yourself.
