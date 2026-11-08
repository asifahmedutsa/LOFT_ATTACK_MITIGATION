# Exploratory: FEVER (lossless federated XGBoost) against the reimplemented baselines, existing testbed runs

**Not preregistered; unpaired.** Added 8 November 2026 at the user's request, before the final
campaign. Same testbed and summarizer for every row (T1B at 600 pps, tree, 300 s, attack at 50 s;
testbed/summarize_run.py unchanged since 6 November 08:38), but different seeds: baselines, none
and v6+PG from the v5 campaign (seeds 4140-4144; rDefender 4140-4142; FTOP and FloRa one run,
4140), v6 and FEVER from the deployment check (4181-4182). The baselines' detectors were trained on
simulator rows; FEVER's on testbed rows. FTODefender has no testbed run. FEVER blocked no benign host in any run; the field
is not written for the baselines' own blocking, so it is left out.
Harm: mean (min-max). Occ.: attack share after onset, mean over s11-s13.

| Traffic | Method | Runs | Harm % | Occ. 3 sw % | s11 avg % | s11 max % | Lost first % | Probe % |
|---|---|---|---|---|---|---|---|---|
| A2 | none | 5 | 10.29 (8.20-11.44) | 40.2 | 58.4 | 94.8 | 21.61 | 30.3 |
| A2 | DMS-BTT | 5 | 0.02 (0.00-0.06) | 26.1 | 18.7 | 54.3 | 19.95 | 31.0 |
| A2 | FTMaster | 5 | 0.01 (0.00-0.03) | 23.7 | 10.0 | 58.1 | 9.90 | 27.2 |
| A2 | FTOP | 1 | 0.08 (0.08-0.08) | 30.9 | 33.9 | 86.9 | 35.69 | 21.9 |
| A2 | FloRa | 1 | 0.05 (0.05-0.05) | 30.7 | 39.1 | 71.5 | 28.06 | 24.3 |
| A2 | rDefender | 3 | 2.82 (1.60-3.55) | 31.0 | 38.6 | 87.6 | 25.45 | 26.1 |
| A2 | v6+PG (sim CatBoost) | 5 | 0.01 (0.00-0.03) | 23.5 | 5.7 | 47.0 | 2.55 | 68.0 |
| A2 | v6 (sim CatBoost) | 2 | 0.01 (0.00-0.01) | 24.7 | 5.9 | 46.9 | 1.48 | 59.0 |
| A2 | FEVER (lossless FL) | 2 | 0.01 (0.00-0.01) | 24.8 | 5.7 | 46.8 | 0.71 | 73.9 |
| A4 | none | 5 | 6.03 (2.61-8.43) | 36.2 | 54.8 | 91.4 | 26.29 | 32.3 |
| A4 | DMS-BTT | 5 | 2.09 (1.28-3.78) | 34.2 | 47.6 | 86.2 | 30.36 | 27.7 |
| A4 | FTMaster | 5 | 4.16 (2.16-5.42) | 35.1 | 53.4 | 91.4 | 30.34 | 30.4 |
| A4 | FTOP | 1 | 2.11 (2.11-2.11) | 28.2 | 39.3 | 79.3 | 33.69 | 21.6 |
| A4 | rDefender | 3 | 1.86 (1.17-2.31) | 33.6 | 44.7 | 86.9 | 28.92 | 26.0 |
| A4 | v6+PG (sim CatBoost) | 5 | 0.02 (0.01-0.03) | 24.5 | 16.4 | 74.2 | 8.85 | 30.7 |
| A4 | v6 (sim CatBoost) | 2 | 0.02 (0.01-0.03) | 24.9 | 19.4 | 75.4 | 10.87 | 34.2 |
| A4 | FEVER (lossless FL) | 2 | 0.00 (0.00-0.00) | 23.9 | 6.1 | 48.5 | 1.10 | 64.6 |
| E9P | none | 5 | 14.08 (9.49-16.42) | 50.5 | 73.1 | 97.1 | 36.79 | 13.1 |
| E9P | DMS-BTT | 5 | 3.01 (1.26-3.74) | 44.3 | 59.3 | 94.2 | 47.57 | 11.4 |
| E9P | FTMaster | 5 | 10.22 (6.20-12.58) | 50.0 | 73.3 | 97.0 | 43.19 | 13.3 |
| E9P | rDefender | 3 | 0.82 (0.00-1.83) | 39.9 | 51.8 | 90.6 | 54.79 | 10.2 |
| E9P | v6+PG (sim CatBoost) | 5 | 0.00 (0.00-0.01) | 29.2 | 13.4 | 81.6 | 17.33 | 13.2 |
| E9P | v6 (sim CatBoost) | 2 | 0.03 (0.02-0.04) | 29.1 | 15.1 | 82.6 | 17.59 | 13.8 |
| E9P | FEVER (lossless FL) | 2 | 0.01 (0.00-0.01) | 26.4 | 12.4 | 83.8 | 20.44 | 12.8 |
| benign | none | 5 | 0.00 (0.00-0.00) | 0.0 | 0.0 | 0.0 | 0.00 | 100.0 |
| benign | DMS-BTT | 5 | 0.00 (0.00-0.00) | 0.0 | 0.0 | 0.0 | 0.02 | 100.0 |
| benign | FTMaster | 5 | 0.00 (0.00-0.00) | 0.0 | 0.0 | 0.0 | 0.02 | 100.0 |
| benign | rDefender | 3 | 0.00 (0.00-0.00) | 0.0 | 0.0 | 0.0 | 0.05 | 100.0 |
| benign | v6+PG (sim CatBoost) | 5 | 0.00 (0.00-0.00) | 0.0 | 0.0 | 0.0 | 0.17 | 100.0 |
| benign | v6 (sim CatBoost) | 2 | 0.00 (0.00-0.00) | 0.0 | 0.0 | 0.0 | 0.17 | 100.0 |
| benign | FEVER (lossless FL) | 2 | 0.00 (0.00-0.00) | 0.0 | 0.0 | 0.0 | 0.17 | 100.0 |
