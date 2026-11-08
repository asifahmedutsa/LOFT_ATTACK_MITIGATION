# Deployment check, fourth arm (descriptive): v6 with PortGuard

T1B at 600 pps, seeds 4181-4182, testbed; means of 2 runs. fever: v6 without PortGuard;
ensguard-v6: v6 with PortGuard (both v6's one-shot CatBoost, simulator rows); fever-fl-ll: lossless
federated XGBoost (testbed rows, deployed). Occupancy: attack share of the table after onset, %.

| Traffic | Method | Harm % | Occupancy (3 switches) | s11 | s12 | s13 | Lost first packets % | Probe success % |
|---|---|---|---|---|---|---|---|---|
| A2 | fever | 0.005 | 24.75 | 5.9 | 34.5 | 33.8 | 1.48 | 59.0 |
| A2 | ensguard-v6 | 0.005 | 24.51 | 6.6 | 33.5 | 33.5 | 3.52 | 37.3 |
| A2 | fever-fl-ll | 0.005 | 24.83 | 5.7 | 34.9 | 33.9 | 0.71 | 73.9 |
| A4 | fever | 0.020 | 24.94 | 19.4 | 26.7 | 28.7 | 10.87 | 34.2 |
| A4 | ensguard-v6 | 0.010 | 22.96 | 18.6 | 24.1 | 26.2 | 10.85 | 30.3 |
| A4 | fever-fl-ll | 0.000 | 23.93 | 6.1 | 32.7 | 33.0 | 1.10 | 64.6 |
| E9P | fever | 0.030 | 29.06 | 15.1 | 36.0 | 36.0 | 17.59 | 13.8 |
| E9P | ensguard-v6 | 0.025 | 29.72 | 16.7 | 36.4 | 36.0 | 19.55 | 13.4 |
| E9P | fever-fl-ll | 0.005 | 26.44 | 12.4 | 33.2 | 33.7 | 20.44 | 12.8 |
| benign | all three | 0.000 | 0 | 0 | 0 | 0 | 0.14-0.17 | 100.0 |

Every arm blocked both attackers and no benign host in every attack run.

## Fifth arm: lossless federated XGBoost with PortGuard (fever-fl-ll-pg)

Same traffic and seeds; means of 2 runs. Both blocked both attackers and no benign host in every
attack run; benign-only runs: harm 0 %, probe success 100 % in both.

| Traffic | Method | Harm % | Occupancy (3 switches) | s11 | s12 | s13 | Lost first packets % | Probe success % | First attack block (s, two seeds) |
|---|---|---|---|---|---|---|---|---|---|
| A2 | fever-fl-ll | 0.005 | 24.83 | 5.7 | 34.9 | 33.9 | 0.71 | 73.9 | 67.7, 74.7 |
| A2 | fever-fl-ll-pg | 0.005 | 23.02 | 6.7 | 30.9 | 31.5 | 8.90 | 24.5 | 77.7, 76.1 |
| A4 | fever-fl-ll | 0.000 | 23.93 | 6.1 | 32.7 | 33.0 | 1.10 | 64.6 | 74.7, 79.9 |
| A4 | fever-fl-ll-pg | 0.000 | 20.75 | 7.9 | 25.9 | 28.5 | 9.52 | 25.5 | 99.0, 83.6 |
| E9P | fever-fl-ll | 0.005 | 26.44 | 12.4 | 33.2 | 33.7 | 20.44 | 12.8 | 74.8, 81.3 |
| E9P | fever-fl-ll-pg | 0.015 | 38.68 | 49.8 | 31.7 | 34.6 | 59.75 | 9.3 | 142.9, 130.4 |

With PortGuard the attackers are blocked later (on Aware by about 55 s), the core switch carries
half the table on Aware, and new connections fail more often on every attack (probe success
9-26 % against 13-74 %). FEVER stays without PortGuard.
