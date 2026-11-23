# I built a tool that checks AI answers against their sources. The interesting part was the grading.

AI answers come with citations that look rigorous. Whether the cited page actually says what the
answer claims is a different question, and nobody checks. So I built **claimcheck**: it splits an
answer into one-fact claims, looks up the source each claim cites, asks a language model whether
that source supports the claim, and flags the rest. It also flags citations to sources that were
never provided, with no model involved, because a lookup is enough.

The pipeline took a couple of days. Measuring whether it works took longer, and that is the part
worth writing about.

## The data

I had a chatbot answer 12 science and history questions, each citing two Wikipedia excerpts, then
split the answers into 72 claims. I labeled every claim by hand as supported, contradicted, not
mentioned, or citing a missing source. Then I wrote 41 more claims with deliberate defects: a
changed year, an invented citation, a true fact attributed to the wrong source.

First finding, before any model ran: **13 of the 72 claims (18%) were not supported by the
excerpt they cited**, 5 of them outright contradicted. The excerpts are short, so "not mentioned"
means "not in these 700 words", not "false". It is still a reminder that a citation next to a
sentence proves little.

## Traps I hit, and avoided only because I looked

**Planted failures are easy.** A word-overlap baseline with no model scored 0.98 F1 on my planted
claims. A combined score would have made any judge look great. So organic and planted claims are
reported separately, and the organic number is the headline.

**Split by answer, not by claim.** Claims from one answer share context. Splitting by claim leaks
information between the development and test sets. The split is by answer, and the test set stayed
locked behind a flag until everything else was frozen.

**A confidence interval can lie.** With a handful of development claims from a single answer,
resampling produced an interval of [0.86, 0.86], a perfect-looking range from almost no data. The tool now refuses to print an
interval below five answers.

**One weird reply can kill a paid run.** The model sometimes answered with a correct JSON verdict,
then an unprompted "correction to the formatting", then a second JSON object. A strict parser
crashed halfway through. Now several objects are accepted only if they agree, and a bad reply is
counted instead of fatal.

**My own labels were wrong in places.** Two other raters (Claude and another chatbot) labeled 20
claims and found one real error. I fixed it before running the test set, and wrote down every
label change, including the one I made after seeing a development result.

## Results

On the held-out test claims, Claude Haiku 5.5 reached **F1 0.89** on the 48 organic claims
(95% interval 0.67 to 1.00), against 0.74 (0.50 to 0.94) for the word-overlap baseline. The paired
difference is +0.15, with an interval that just touches zero. So: probably better, not proven.
That organic number rests on 9 flagged claims. One claim moves it by about 0.1.

All four of the judge's errors were organic, and when I read them, I think at least two are bad
labels on my side (I tended to write "contradicted" when the source was merely silent). I did not
change them, because editing the answer key after seeing the model's score is how you fool
yourself. The report lists them for anyone to disagree with.

The whole test run cost $0.02. Everything I spent across the project was about three cents.

## What I would do next

A second human annotator, because one person grading 113 claims is the weakest link. Longer
sources and a different domain. And measuring the claim-splitting stage, which I checked by hand
but did not score.

The code, the labeled dataset with a datasheet, and the full report are in the repo: [link to the
repository].
