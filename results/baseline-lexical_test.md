# baseline-lexical on test (76 claims)

## end_to_end

| slice | n | flagged | precision | recall | F1 (95% CI) | kappa (4-class) |
|---|---|---|---|---|---|---|
| all | 76 | 37 (49%) | 0.92 | 0.92 | 0.92 [0.85, 0.98] | 0.73 |
| organic | 48 | 9 (19%) | 0.70 | 0.78 | 0.74 [0.50, 0.94] | 0.62 |
| planted | 28 | 28 (100%) | 1.00 | 0.96 | 0.98 [0.94, 1.00] | 0.57 |

## judge_only

| slice | n | flagged | precision | recall | F1 (95% CI) | kappa (4-class) |
|---|---|---|---|---|---|---|
| all | 69 | 30 (43%) | 0.90 | 0.90 | 0.90 [0.81, 0.97] | 0.66 |
| organic | 48 | 9 (19%) | 0.70 | 0.78 | 0.74 [0.50, 0.94] | 0.62 |
| planted | 21 | 21 (100%) | 1.00 | 0.95 | 0.98 [0.92, 1.00] | 0.09 |

Citation matcher: caught 7 of 7 missing citations, 0 false alarms.
