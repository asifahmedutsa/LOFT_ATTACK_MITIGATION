# FEVER ablation on the testbed (exploratory)

Plan: docs/fever_ablation_plan.md. T1B, seeds 4140, 4141, 4142. FEVER and FEVER without volume are the v5-campaign runs; FEVER without ML is new. Means over seeds.

| Attack | Variant | harm % | attack share s11 % | lost first pkts % | probe success % | attackers blocked | benign blocked | first attacker block (s) | decision ms |
|---|---|---|---|---|---|---|---|---|---|
| A2 | FEVER | 0.61 | 11.2 | 11.2 | 45.1 | 2.0 | 0.0 | 71 | 58 |
| A2 | FEVER without volume | 0.05 | 13.4 | 13.1 | 46.1 | 2.0 | 0.0 | 71 | 61 |
| A2 | FEVER without ML | 0.84 | 30.0 | 23.9 | 23.9 | 2.0 | 0.0 | 130 | 80 |
| A2 | rDefender | 2.82 | 38.6 | 25.4 | 26.1 | 0.0 | 0.0 | nan | 66 |
| A4 | FEVER | 0.05 | 25.2 | 17.6 | 29.7 | 2.0 | 0.0 | 125 | 30 |
| A4 | FEVER without volume | 1.11 | 49.3 | 29.4 | 29.7 | 0.0 | 0.0 | nan | 53 |
| A4 | FEVER without ML | 0.07 | 27.7 | 16.4 | 28.2 | 2.0 | 0.0 | 135 | 38 |
| A4 | rDefender | 1.86 | 44.7 | 28.9 | 26.0 | 0.0 | 0.0 | nan | 56 |
| E9P | FEVER | 0.16 | 26.7 | 27.4 | 12.3 | 2.0 | 0.0 | 68 | 48 |
| E9P | FEVER without volume | 3.89 | 67.6 | 48.4 | 12.6 | 0.0 | 0.0 | nan | 103 |
| E9P | FEVER without ML | 0.00 | 43.3 | 53.3 | 10.2 | 1.3 | 0.0 | 124 | 64 |
| E9P | rDefender | 0.82 | 51.8 | 54.8 | 10.2 | 0.0 | 0.0 | nan | 70 |
| benign | FEVER | 0.00 | 0.0 | 0.1 | 100.0 | 0.0 | 0.0 | nan | 7 |
| benign | FEVER without volume | 0.00 | 0.0 | 0.1 | 100.0 | 0.0 | 0.0 | nan | 7 |
| benign | FEVER without ML | 0.00 | 0.0 | 0.0 | 100.0 | 0.0 | 0.0 | nan | 8 |
| benign | rDefender | 0.00 | 0.0 | 0.0 | 100.0 | 0.0 | 0.0 | nan | 8 |

## Paired wins of FEVER (lower is better), per attack

| Against | Measure | A2 | A4 | E9P | all |
|---|---|---|---|---|---|
| FEVER without volume | harm | 1/3 | 3/3 | 3/3 | 7/9 |
| FEVER without volume | attack share | 2/3 | 3/3 | 3/3 | 8/9 |
| FEVER without ML | harm | 1/3 | 1/3 | 0/3 | 2/9 |
| FEVER without ML | attack share | 3/3 | 3/3 | 2/3 | 8/9 |
| rDefender | harm | 3/3 | 3/3 | 2/3 | 8/9 |
| rDefender | attack share | 3/3 | 3/3 | 3/3 | 9/9 |

## Every run

| Seed | Attack | Variant | harm % | share % | attackers blocked | benign blocked | first block (s) |
|---|---|---|---|---|---|---|---|
| 4140 | A2 | FEVER | 0.96 | 14.5 | 2 | 0 | 67.1 |
| 4140 | A2 | FEVER without volume | 0.00 | 11.2 | 2 | 0 | 66.1 |
| 4140 | A2 | FEVER without ML | 0.36 | 33.3 | 2 | 0 | 125.2 |
| 4140 | A2 | rDefender | 1.60 | 40.8 | 0 | 0 | - |
| 4140 | A4 | FEVER | 0.04 | 25.0 | 2 | 0 | 124.3 |
| 4140 | A4 | FEVER without volume | 2.06 | 43.1 | 0 | 0 | - |
| 4140 | A4 | FEVER without ML | 0.00 | 26.3 | 2 | 0 | 130.9 |
| 4140 | A4 | rDefender | 1.17 | 39.9 | 0 | 0 | - |
| 4140 | E9P | FEVER | 0.01 | 27.8 | 2 | 0 | 78.1 |
| 4140 | E9P | FEVER without volume | 0.68 | 67.8 | 0 | 0 | - |
| 4140 | E9P | FEVER without ML | 0.00 | 51.8 | 2 | 0 | 182.8 |
| 4140 | E9P | rDefender | 0.00 | 56.3 | 0 | 0 | - |
| 4140 | benign | FEVER | 0.00 | 0.0 | 0 | 0 | - |
| 4140 | benign | FEVER without volume | 0.00 | 0.0 | 0 | 0 | - |
| 4140 | benign | FEVER without ML | 0.00 | 0.0 | 0 | 0 | - |
| 4140 | benign | rDefender | 0.00 | 0.0 | 0 | 0 | - |
| 4141 | A2 | FEVER | 0.84 | 8.6 | 2 | 0 | 69.1 |
| 4141 | A2 | FEVER without volume | 0.03 | 10.3 | 2 | 0 | 70.3 |
| 4141 | A2 | FEVER without ML | 0.45 | 28.7 | 2 | 0 | 126.0 |
| 4141 | A2 | rDefender | 3.55 | 33.5 | 0 | 0 | - |
| 4141 | A4 | FEVER | 0.03 | 25.0 | 2 | 0 | 133.1 |
| 4141 | A4 | FEVER without volume | 1.00 | 52.2 | 0 | 0 | - |
| 4141 | A4 | FEVER without ML | 0.00 | 25.3 | 2 | 0 | 130.1 |
| 4141 | A4 | rDefender | 2.11 | 49.8 | 0 | 0 | - |
| 4141 | E9P | FEVER | 0.03 | 21.9 | 2 | 0 | 62.0 |
| 4141 | E9P | FEVER without volume | 4.11 | 66.6 | 0 | 0 | - |
| 4141 | E9P | FEVER without ML | 0.00 | 21.7 | 2 | 0 | 65.5 |
| 4141 | E9P | rDefender | 0.63 | 49.4 | 0 | 0 | - |
| 4141 | benign | FEVER | 0.00 | 0.0 | 0 | 0 | - |
| 4141 | benign | FEVER without volume | 0.00 | 0.0 | 0 | 0 | - |
| 4141 | benign | FEVER without ML | 0.00 | 0.0 | 0 | 0 | - |
| 4141 | benign | rDefender | 0.00 | 0.0 | 0 | 0 | - |
| 4142 | A2 | FEVER | 0.02 | 10.6 | 2 | 0 | 78.1 |
| 4142 | A2 | FEVER without volume | 0.11 | 18.6 | 2 | 0 | 77.4 |
| 4142 | A2 | FEVER without ML | 1.72 | 28.0 | 2 | 0 | 138.7 |
| 4142 | A2 | rDefender | 3.31 | 41.6 | 0 | 0 | - |
| 4142 | A4 | FEVER | 0.08 | 25.7 | 2 | 0 | 117.1 |
| 4142 | A4 | FEVER without volume | 0.28 | 52.7 | 0 | 0 | - |
| 4142 | A4 | FEVER without ML | 0.21 | 31.6 | 2 | 0 | 142.9 |
| 4142 | A4 | rDefender | 2.31 | 44.4 | 0 | 0 | - |
| 4142 | E9P | FEVER | 0.45 | 30.4 | 2 | 0 | 64.3 |
| 4142 | E9P | FEVER without volume | 6.89 | 68.3 | 0 | 0 | - |
| 4142 | E9P | FEVER without ML | 0.00 | 56.5 | 0 | 0 | - |
| 4142 | E9P | rDefender | 1.83 | 49.6 | 0 | 0 | - |
| 4142 | benign | FEVER | 0.00 | 0.0 | 0 | 0 | - |
| 4142 | benign | FEVER without volume | 0.00 | 0.0 | 0 | 0 | - |
| 4142 | benign | FEVER without ML | 0.00 | 0.0 | 0 | 0 | - |
| 4142 | benign | rDefender | 0.00 | 0.0 | 0 | 0 | - |
