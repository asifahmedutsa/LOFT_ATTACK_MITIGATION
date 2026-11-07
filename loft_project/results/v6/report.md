# FEVER v6 on the testbed (T1B, seeds 4140-4144, 5 runs per cell)

## A2

| Method | Harm % | Avg attack share % | Max attack share % | First packets lost % | New connections ok % | Benign hosts blocked |
|---|---|---|---|---|---|---|
| FEVER v6 | 0.01 | 5.72 | 46.99 | 2.55 | 68.03 | 0.00 |
| FEVER v5 | 1.05 | 12.62 | 84.74 | 14.16 | 47.40 | 0.00 |
| DMS-BTT | 0.02 | 18.67 | 54.28 | 19.95 | 31.05 | 0.00 |
| FTMaster | 0.01 | 9.98 | 58.10 | 9.90 | 27.24 | 0.00 |

## A4

| Method | Harm % | Avg attack share % | Max attack share % | First packets lost % | New connections ok % | Benign hosts blocked |
|---|---|---|---|---|---|---|
| FEVER v6 | 0.02 | 16.38 | 74.22 | 8.85 | 30.71 | 0.00 |
| FEVER v5 | 0.32 | 27.23 | 80.04 | 16.01 | 29.45 | 0.00 |
| DMS-BTT | 2.09 | 47.58 | 86.21 | 30.36 | 27.74 | 0.00 |
| FTMaster | 4.16 | 53.36 | 91.42 | 30.34 | 30.41 | 0.00 |

## E9P

| Method | Harm % | Avg attack share % | Max attack share % | First packets lost % | New connections ok % | Benign hosts blocked |
|---|---|---|---|---|---|---|
| FEVER v6 | 0.00 | 13.44 | 81.61 | 17.33 | 13.22 | 0.00 |
| FEVER v5 | 0.10 | 25.96 | 83.80 | 29.15 | 12.56 | 0.00 |
| DMS-BTT | 3.01 | 59.30 | 94.23 | 47.57 | 11.37 | 0.00 |
| FTMaster | 10.22 | 73.29 | 96.97 | 43.19 | 13.30 | 0.00 |

## A2 + A4 + E9P

| Method | Harm % | Avg attack share % | Max attack share % | First packets lost % | New connections ok % | Benign hosts blocked |
|---|---|---|---|---|---|---|
| FEVER v6 | 0.01 | 11.85 | 67.60 | 9.58 | 37.32 | 0.00 |
| FEVER v5 | 0.49 | 21.94 | 82.86 | 19.77 | 29.81 | 0.00 |
| DMS-BTT | 1.71 | 41.85 | 78.24 | 32.63 | 23.39 | 0.00 |
| FTMaster | 4.80 | 45.54 | 82.16 | 27.81 | 23.65 | 0.00 |

## Benign only

| Method | Harm % | Avg attack share % | Max attack share % | First packets lost % | New connections ok % | Benign hosts blocked |
|---|---|---|---|---|---|---|
| FEVER v6 | 0.00 | 0.00 | 0.00 | 0.17 | 100.00 | 0.00 |
| FEVER v5 | 0.00 | 0.00 | 0.00 | 0.12 | 100.00 | 0.00 |
| DMS-BTT | 0.00 | 0.00 | 0.00 | 0.02 | 100.00 | 0.00 |
| FTMaster | 0.00 | 0.00 | 0.00 | 0.02 | 100.00 | 0.00 |

## v6 against v5, run by run (attack runs)

| Metric | v6 better | equal | v5 better |
|---|---|---|---|
| Harm % | 10 | 4 | 1 |
| Avg attack share % | 15 | 0 | 0 |
| Max attack share % | 10 | 0 | 5 |
| First packets lost % | 13 | 0 | 2 |
| New connections ok % | 11 | 1 | 3 |
