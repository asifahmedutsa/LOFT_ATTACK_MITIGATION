# v4-lite testbed development check (seeds 4134-4136, before the preregistration)

| Run | harm % | lost first packets % | attack share s11 % | probe success % | decision ms (mean) | hosts blocked |
|---|---|---|---|---|---|---|
| A4 s4134 | 2.80 | 27.31 | 45.05 | 23.64 | 61 | none |
| A4 s4135 | 3.55 | 28.16 | 35.23 | 20.62 | 46 | none |
| A4 s4136 | 0.16 | 25.12 | 47.39 | 14.45 | 75 | none |
| benign s4134 | 0.00 | 0.01 | 0 | 100 | 11 | none |
| benign s4135 | 0.00 | 0.12 | 0 | 100 | 10 | none |
| benign s4136 | 0.00 | 0.08 | 0 | 100 | 9 | none |

Reference, v3 ensguard under A4 on the v3 test seeds 4120-4124 (other seeds, not a test):
harm 7.63 %, lost first packets 25.0 %, attack share 47.4 %, probe success 27.5 %, decision 114-161 ms,
benign hosts blocked in 3 of 5 runs.
