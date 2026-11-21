# Datasheet: claimcheck labeled claims (v1)

Follows the "Datasheets for Datasets" questions, shortened. Last updated 2026-11-21.
Items marked **TO FILL** depend on steps not done yet and are listed at the end.

## Motivation

- **Purpose.** Measure how well a judge flags claims in an AI answer that its cited source does
  not support. The positive class is "flagged": any label except `SUPPORTED`.
- **Who made it and why.** One person (Amir Pourshafiee) as a portfolio project. It was not
  commissioned and has no funding.

## Composition

- **Unit.** One atomic claim from an AI-written answer, with the source it cites.
- **Size.** 113 claims: 72 organic (taken from AI answers as written) and 41 planted (written by
  the annotator to include known failure modes). 12 questions, 24 source excerpts, 2 sources per
  question.
- **Sources.** The first 700 words (whole paragraphs only, so 694 to about 700) of 24 English
  Wikipedia articles, two per question. Each file in `eval/sources/` has a header with the
  permanent revision link (`oldid`) and retrieval date (2026-11-20). Topics are science and
  engineering history (Antikythera mechanism, Voyager probes, Panama and Suez canals, Enigma,
  Apollo 11 and 13, and so on). The full list is `eval/topics.json`.
- **Labels (4 classes).**

| Label | Total | dev | test |
|---|---|---|---|
| SUPPORTED | 59 | 20 | 39 |
| NOT_MENTIONED | 27 | 8 | 19 |
| CONTRADICTED | 17 | 6 | 11 |
| CITATION_MISSING | 10 | 3 | 7 |
| **Total** | **113** | **37** | **76** |

- **Organic vs planted.** Organic: 72 claims (dev 24, test 48), of which 13 (18%) are flagged by
  the hand labels: 7 NOT_MENTIONED and 6 CONTRADICTED. That is the real finding about the
  answer-writing chatbot on these excerpts. Planted: 41 claims (dev 13, test 28), 100% flagged
  by construction.
- **Planted types** (written by the annotator after all organic rows were labeled):
  `contradiction` 11, `unsupported_addition` 9, `wrong_source` 11, `fake_citation` 10.
  A `fake_citation` row cites `S3`, which was never provided, and is labeled `CITATION_MISSING`.
  A `wrong_source` row is a true statement taken from the other source, cited to the wrong one.
- **Splits.** `dev` is q07 to q10 (37 claims) and `test` is q01 to q06, q11, q12 (76 claims).
  The split is by answer, not by claim, so claims of one answer never straddle the line. Which
  four answers went to dev was drawn with a seeded random generator (seed 20261120). Planted rows
  inherit the split of their answer.
- **Confidential or personal data.** None. All text is public Wikipedia text and AI output.

## Collection process

1. **Answers.** A chatbot ("Grok Bot", model name not shown in the app) was shown each question and
   only the two source titles, and wrote 5 to 6 sentences with one `[S#]` marker per sentence,
   from memory. Generated 2026-11-20. Prompts: `eval/prompts/01_generate_answers.md`.
2. **Claims.** The same chat split each answer into atomic claims
   (`eval/prompts/02_split_claims.md`), at most 3 per citation per answer, in order. The annotator
   checked each split and did not add or drop claims by difficulty. Raw output:
   `eval/dataset/claims_raw.csv`. The first version of this prompt capped claims "in order", which
   gave 71 of 72 claims to S1; the cap was changed to per citation and the split redone (36 and
   36 now).
3. **Labels.** One annotator labeled each organic claim from the cited excerpt only, using
   `eval/LABELING_GUIDE.md`, without running any model first. Planted rows were added only after
   all organic rows were labeled.
4. **Evidence quotes** (optional, at most about 15 words) were recorded for SUPPORTED and
   CONTRADICTED rows. No metric uses them, and 22 exceed 15 words (validator warnings).

## Preprocessing and fixes made along the way

- **Split column repair.** An early spreadsheet export put 20 planted rows in `dev`, and a later
  export reverted the same fix. They were corrected from `eval/topics.json` with
  `python -m claimcheck.labelsheet fix-splits`, which rewrites only the split column. Run it
  after any spreadsheet round trip.
- **Label edits after first pass.**
  - `q11-c03` NOT_MENTIONED to SUPPORTED, after re-reading the article, before any model output
    was seen.
  - `q10-c02` SUPPORTED to CONTRADICTED on 2026-11-21, **after seeing judge output on dev**. The
    source says "porcelain materials" and the claim says "baked clay"; equating them needs outside
    knowledge. The row's `notes` cell records this.
  - `q07-c05` was **not** changed although the judge disagrees with the label. The excerpt says
    both "closed later that day" and "closure ... only two days after opening", so the label is a
    judgment call.

## Uses

- **Intended.** Evaluating claim-versus-source judges, practicing evaluation design, and as a
  teaching example of honest small-set reporting.
- **Not suitable for.** Estimating real-world hallucination rates, comparing chatbots, or any
  claim about topics outside short Wikipedia excerpts.

## Limitations (read these before quoting any number)

1. **Small.** 113 claims, 54 flagged (13 of them organic). Confidence intervals are wide. The dev split has only 4
   answers, so no interval can be computed for it.
2. **One annotator.** There is no second rater. The consistency check below is the only
   reliability estimate, and it measures the same person's repeatability, not correctness.
3. **"Not mentioned" means "not in a 700-word excerpt".** A claim can be true and still be
   flagged because the excerpt is truncated. The judge sees the same excerpt, so the metric is
   fair for this task, but it is not a measure of truth.
4. **Planted rows are easier than organic ones.** They are blunt (a changed year, a made-up
   citation), and a word-overlap baseline scores 0.95 F1 on them in dev. Planted rows are 37% of the
   test split. Organic and planted results are always reported separately, and the headline
   number is the organic one.
5. **Fake citations are caught by a lookup**, not by a judge. They appear in an `end_to_end` view
   and are removed from the `judge_only` view.
6. **One generator model, one claim splitter.** All answers come from one chatbot and the same
   chat split them, so its habits (for example claim granularity) shape the data. The judge is a
   different model family, which avoids self-preference, but the generator's errors are
   specific to that model and day.
7. **Pretraining overlap.** Wikipedia is in the training data of every large model, so a judge
   could answer from memory instead of the excerpt. The labeling rules and the judge prompt both
   say "use only the excerpt", which is checked only indirectly (the judge must quote the
   excerpt, and a quote not found in it is discarded).
8. **Ambiguous cases exist** (see the two examples above). They are left in, not removed.

## Distribution and license

- **Excerpts.** Wikipedia text, CC BY-SA 4.0. Attribution and revision links are in each file
  header. Any redistribution of the excerpts must stay under the same license.
- **Claims, labels, notes.** Written for this project. Because the claims paraphrase the CC BY-SA
  excerpts, treat the dataset as CC BY-SA 4.0 too. The code is MIT. This is the author's
  reading, not legal advice.
- **Generated answers.** Produced by a third-party chatbot. Its terms of use for outputs were not
  checked. **TO FILL:** read them before publishing `eval/answers/answers_raw.md`.

## Maintenance

Version 1, 2026-11-21. Label corrections are made by pull request and must be listed in the
"Label edits" section above with the reason and whether judge output had been seen.

## Still to fill in

- **Intra-annotator consistency (Cohen's kappa, 20 organic claims relabeled blind at least 24
  hours later):** TO FILL from `python -m claimcheck.consistency compare`.
- **Generator model name:** the app did not show it. If it can be found later, add it.
- Confirm the generated answers' terms of use (above).
