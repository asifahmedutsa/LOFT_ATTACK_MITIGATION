# Exploratory: offline metrics of the reimplemented baselines on testbed rows

**Not preregistered.** 8 November 2026, loftbench/tbfl_baselines.py. T1B test rows of the testbed
recordings (seeds 4176-4178), as results/tbfl/report.md. Per-rule classifiers only (each baseline's own
features and model); the table-state detectors are not scored. Training: simulator T1A rows (the models
the testbed runs used), C3's testbed rows (as each paper: one controller, one trace), or C1-C3's testbed
rows pooled (FEVER's data, shared raw). False alarms: benign rows of the benign-only test runs.
FTODefender is missing: its training ran out of memory twice on this 8 GB machine.

| Method | Training | Threshold | False alarms % | Acc. | Prec. | Rec. | F1 | MCC | G1 | G2 | G3 | Mimic | Spoof | Slow | Pulse | Aware |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FEVER (lossless federated XGBoost) | testbed, C1-C3 federated | 0.1 % T1A benign | 0.79 | 83.73 | 99.74 | 76.82 | 86.79 | 0.70 | 99.96 | 100.00 | 99.87 | 60.93 | 99.85 | 9.20 | 99.95 | 25.43 |
| FTMaster | simulator T1A rows | 0.5 | 0.11 | 73.89 | 99.92 | 62.53 | 76.92 | 0.58 | 96.70 | 97.83 | 97.42 | 0.01 | 97.13 | 0.02 | 93.54 | 0.00 |
| FTMaster | simulator T1A rows | 0.1 % T1A benign | 0.06 | 71.71 | 99.94 | 59.37 | 74.49 | 0.55 | 92.98 | 94.30 | 93.56 | 0.00 | 93.60 | 0.00 | 83.24 | 0.00 |
| FTMaster | testbed, C3 only | 0.5 | 0.33 | 75.32 | 99.80 | 64.66 | 78.48 | 0.60 | 99.86 | 99.91 | 99.85 | 0.07 | 99.80 | 0.09 | 99.87 | 0.05 |
| FTMaster | testbed, C3 only | 0.1 % T1A benign | 0.19 | 73.48 | 99.89 | 61.95 | 76.48 | 0.57 | 96.79 | 96.80 | 96.29 | 0.02 | 96.71 | 0.04 | 91.46 | 0.02 |
| FTMaster | testbed, C1-C3 pooled | 0.5 | 3.09 | 89.40 | 98.36 | 86.20 | 91.88 | 0.78 | 99.93 | 99.91 | 99.86 | 88.18 | 99.85 | 83.17 | 99.86 | 24.90 |
| FTMaster | testbed, C1-C3 pooled | 0.1 % T1A benign | 0.22 | 80.95 | 99.83 | 72.74 | 84.16 | 0.67 | 95.60 | 95.96 | 95.25 | 64.48 | 95.65 | 35.33 | 88.81 | 4.21 |
| FTOP | simulator T1A rows | 0.5 | 0.11 | 74.04 | 99.92 | 62.74 | 77.08 | 0.58 | 97.20 | 98.18 | 97.74 | 0.01 | 97.49 | 0.02 | 93.63 | 0.00 |
| FTOP | simulator T1A rows | 0.1 % T1A benign | 0.05 | 66.43 | 99.95 | 51.78 | 68.22 | 0.50 | 84.42 | 84.84 | 77.32 | 0.00 | 80.66 | 0.00 | 72.10 | 0.00 |
| FTOP | testbed, C3 only | 0.5 | 0.32 | 75.35 | 99.84 | 64.67 | 78.49 | 0.60 | 99.92 | 99.91 | 99.85 | 0.06 | 99.83 | 0.09 | 99.86 | 0.04 |
| FTOP | testbed, C3 only | 0.1 % T1A benign | 0.00 | 30.43 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| FTOP | testbed, C1-C3 pooled | 0.5 | 3.65 | 88.89 | 98.16 | 85.63 | 91.47 | 0.77 | 99.92 | 99.91 | 99.85 | 88.80 | 99.84 | 84.96 | 99.86 | 19.40 |
| FTOP | testbed, C1-C3 pooled | 0.1 % T1A benign | 0.00 | 30.43 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| FloRa | simulator T1A rows | 0.5 | 0.11 | 73.97 | 99.94 | 62.62 | 77.00 | 0.58 | 97.17 | 98.07 | 97.47 | 0.01 | 97.58 | 0.02 | 93.02 | 0.00 |
| FloRa | simulator T1A rows | 0.1 % T1A benign | 0.08 | 71.19 | 99.96 | 58.61 | 73.90 | 0.55 | 92.12 | 93.55 | 92.41 | 0.00 | 92.97 | 0.00 | 80.59 | 0.00 |
| FloRa | testbed, C3 only | 0.5 | 0.32 | 75.34 | 99.82 | 64.68 | 78.50 | 0.60 | 99.93 | 99.91 | 99.87 | 0.06 | 99.86 | 0.09 | 99.86 | 0.04 |
| FloRa | testbed, C3 only | 0.1 % T1A benign | 0.13 | 73.27 | 99.91 | 61.63 | 76.23 | 0.57 | 96.50 | 96.42 | 95.92 | 0.00 | 96.37 | 0.01 | 90.37 | 0.00 |
| FloRa | testbed, C1-C3 pooled | 0.5 | 2.58 | 87.50 | 98.75 | 83.09 | 90.25 | 0.75 | 99.93 | 99.91 | 99.86 | 87.09 | 99.85 | 77.79 | 99.86 | 7.32 |
| FloRa | testbed, C1-C3 pooled | 0.1 % T1A benign | 0.20 | 79.26 | 99.87 | 70.28 | 82.51 | 0.65 | 94.94 | 95.50 | 94.54 | 60.78 | 95.30 | 22.50 | 86.13 | 1.89 |
| DMS-BTT | simulator T1A rows | 0.5 | 0.11 | 74.17 | 99.92 | 62.92 | 77.21 | 0.58 | 97.59 | 98.37 | 98.00 | 0.01 | 97.85 | 0.02 | 93.79 | 0.00 |
| DMS-BTT | simulator T1A rows | 0.1 % T1A benign | 0.06 | 71.70 | 99.94 | 59.36 | 74.48 | 0.55 | 93.16 | 94.34 | 93.61 | 0.00 | 93.81 | 0.00 | 82.58 | 0.00 |
| DMS-BTT | testbed, C3 only | 0.5 | 0.32 | 75.35 | 99.82 | 64.68 | 78.50 | 0.60 | 99.93 | 99.92 | 99.87 | 0.07 | 99.86 | 0.09 | 99.86 | 0.05 |
| DMS-BTT | testbed, C3 only | 0.1 % T1A benign | 0.16 | 73.37 | 99.90 | 61.78 | 76.35 | 0.57 | 96.73 | 96.61 | 96.08 | 0.00 | 96.53 | 0.01 | 90.84 | 0.00 |
| DMS-BTT | testbed, C1-C3 pooled | 0.5 | 3.25 | 87.85 | 98.31 | 83.98 | 90.58 | 0.76 | 99.93 | 99.91 | 99.87 | 87.86 | 99.85 | 79.47 | 99.86 | 11.90 |
| DMS-BTT | testbed, C1-C3 pooled | 0.1 % T1A benign | 0.30 | 78.10 | 99.81 | 68.65 | 81.35 | 0.63 | 94.75 | 95.06 | 94.33 | 56.58 | 94.90 | 13.57 | 84.56 | 1.76 |

FTOP at the 0.1 % rule (C3 only, pooled): its random forest gives probability 1.0 to more than 0.1 % of
the T1A benign rows, so the threshold lands above every score and nothing is flagged; the rule does not
apply to it. FEVER's false alarms here, 0.79 %, differ from report.md's 0.72 % at the same recall; the
cause is not yet found.

## FTMaster's detector trained by lossless federation (exploratory, 8 November)

FTMaster's six features and settings (XGBoost, 200 trees, depth 6, eta 0.3), trained with
fl/run_fedxgb_hist.py on C1-C3's testbed rows (three workers, histogram sums; 0.66 GB loopback
traffic, 24 s), scored by loftbench/tbfl_ftm_fed.py.

| Detector | Threshold | False alarms % | Recall | F1 | MCC | Mimic | Slow | Aware |
|---|---|---|---|---|---|---|---|---|
| FEVER (lossless federated, 17 features) | 0.1 % T1A benign | 0.79 | 76.82 | 86.79 | 0.70 | 60.93 | 9.20 | 25.43 |
| FTMaster, lossless federated | 0.1 % T1A benign | 0.25 | 73.12 | 84.41 | 0.67 | 64.57 | 37.45 | 3.25 |
| FTMaster, pooled (no privacy) | 0.1 % T1A benign | 0.22 | 72.74 | 84.16 | 0.67 | 64.48 | 35.33 | 4.21 |
| FTMaster, lossless federated | 0.5 | 3.07 | 86.05 | 91.81 | 0.78 | 87.78 | 82.82 | 24.36 |
| FTMaster, pooled (no privacy) | 0.5 | 3.09 | 86.20 | 91.88 | 0.78 | 88.18 | 83.17 | 24.90 |
| FTMaster, C3 only (its paper) | 0.5 | 0.33 | 64.66 | 78.48 | 0.60 | 0.07 | 0.09 | 0.05 |

Federated and pooled FTMaster agree within 0.4 points on every measure but are not the same model
row by row (largest difference in one row's probability 0.998): the workers' merged quantile sketch
gives slightly different bins from single-machine training.
