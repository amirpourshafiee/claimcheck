# Resume bullets (every number is in EVALUATION.md)

Pick three or four. Keep the caveats if asked in an interview.

1. Built **claimcheck**, an open-source Python tool that splits an AI answer into atomic claims,
   matches each to its cited source, and flags claims the source contradicts, never mentions, or
   cites a source that was never provided; 138 pytest tests, mocked LLM calls, GitHub Actions CI.

2. Hand-labeled a 113-claim evaluation set (72 organic, 41 planted failures; 12 answers, 24
   Wikipedia excerpts) with a datasheet and answer-level train/test split; found that **18% of an
   AI chatbot's organic claims were unsupported by the source it cited**.

3. Evaluated a Claude Haiku 5.5 judge on a held-out split: **F1 0.89 (95% CI 0.67 to 1.00)** on
   organic claims versus 0.74 for a word-overlap baseline, paired gain +0.15 (CI 0.00 to 0.31);
   reported organic and planted claims separately because planted ones are trivially easy.

4. Designed the evaluation for honesty and low cost: answer-level bootstrap intervals withheld
   below 5 answers, a locked test split, call caps with cost estimates, every post-hoc label change
   disclosed; the full project ran for about $0.03 in API spend.

Interview-safe one-liners for the weak spots:
- "The organic test result rests on 9 flagged claims, so I report the interval and call the gain
  suggestive, not proven."
- "All four judge errors looked like borderline or wrong labels, and I did not change them after
  seeing test output."
