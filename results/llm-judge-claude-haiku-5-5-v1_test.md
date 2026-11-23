# llm-judge-claude-haiku-5-5-v1 on test (76 claims)

## end_to_end

| slice | n | flagged | precision | recall | F1 (95% CI) | kappa (4-class) |
|---|---|---|---|---|---|---|
| all | 76 | 37 (49%) | 0.97 | 0.97 | 0.97 [0.94, 1.00] | 0.92 |
| organic | 48 | 9 (19%) | 0.89 | 0.89 | 0.89 [0.67, 1.00] | 0.74 |
| planted | 28 | 28 (100%) | 1.00 | 1.00 | 1.00 [1.00, 1.00] | 1.00 |

## judge_only

| slice | n | flagged | precision | recall | F1 (95% CI) | kappa (4-class) |
|---|---|---|---|---|---|---|
| all | 69 | 30 (43%) | 0.97 | 0.97 | 0.97 [0.92, 1.00] | 0.90 |
| organic | 48 | 9 (19%) | 0.89 | 0.89 | 0.89 [0.67, 1.00] | 0.74 |
| planted | 21 | 21 (100%) | 1.00 | 1.00 | 1.00 [1.00, 1.00] | 1.00 |

Citation matcher: caught 7 of 7 missing citations, 0 false alarms.
