# Secure aggregation and a federated threshold

docs/secagg_plan.md. T1B test rows, seeds 4176-4178 (1,455,489 rows, 69,377 benign).

## S1 Exactness

- Trees of the four runs (masked, unmasked, and each rerun with fresh keys) identical in split feature, cut, default direction and leaf value: yes
- Scores identical on every test row: yes
- S1: pass

## S2 Fidelity (threshold rule tau_C3)

| Model | Accuracy | Precision | Recall | F1 | False alarms |
|---|---|---|---|---|---|
| Lossless federated XGBoost | 83.73 | 99.74 | 76.82 | 86.79 | 0.79 |
| Secure-aggregation trainer | 83.70 | 99.74 | 76.77 | 86.76 | 0.78 |

- F1 within 1.0 point: pass (difference 0.03)
- Recall within 1.0 point: pass (difference 0.04)
- Agreement on at least 99 % of test rows: pass (99.03 %)

## S3 Cost (reported, not tested)

| Run | Training (s) | Masking (s, slowest controller) | Payload (MB) | Loopback (MB) |
|---|---|---|---|---|
| masked | 796.3 | 6.99 | 6320 | 6331 |
| unmasked | 779.6 | 0.00 | 6320 | 6331 |
| masked_s1 | 790.5 | 6.64 | 6320 | 6331 |
| unmasked_s1 | 784.9 | 0.00 | 6320 | 6331 |
| fl/run_fedxgb_hist.py (XGBoost, clear) | 37.5 | – | – | 2601 |

- Masked payload +0.0 % against unmasked (expected within 5 %); masked time +2.1 % (expected within 25 %).
- The trainer is written in NumPy and XGBoost in C++, so the training times differ by the implementation, not by the masking. The trainer sends every node's full histogram, where XGBoost builds one child's histogram and subtracts it from the parent's, so it sends more bytes.

## T1 Threshold (T1B benign test rows; budget 0.1 %)

| Model | Threshold | tau | False alarms % | per seed (4176, 4177, 4178) | UHt false alarms % | Recall % | F1 % | Recall G1 | Recall G2 | Recall G3 | Recall Mimic | Recall Spoof | Recall Slow | Recall Pulse | Recall Aware |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Lossless federated XGBoost | tau_C3 | 0.495290 | 0.794 | 0.844, 0.806, 0.735 | 0.155 | 76.82 | 86.79 | 100.0 | 100.0 | 99.9 | 60.9 | 99.9 | 9.2 | 100.0 | 25.4 |
| Lossless federated XGBoost | tau_max | 0.636603 | 0.564 | 0.603, 0.560, 0.528 | 0.058 | 75.83 | 86.18 | 99.9 | 100.0 | 99.8 | 59.1 | 99.8 | 6.3 | 99.9 | 21.9 |
| Lossless federated XGBoost | tau_fed | 0.557741 | 0.689 | 0.713, 0.722, 0.634 | 0.077 | 76.38 | 86.52 | 100.0 | 100.0 | 99.8 | 60.2 | 99.8 | 7.8 | 100.0 | 23.9 |
| Secure-aggregation trainer | tau_C3 | 0.507999 | 0.778 | 0.778, 0.828, 0.731 | 0.077 | 76.77 | 86.76 | 100.0 | 100.0 | 99.8 | 60.4 | 99.8 | 8.6 | 99.9 | 25.9 |
| Secure-aggregation trainer | tau_max | 0.655628 | 0.551 | 0.564, 0.587, 0.503 | 0.058 | 75.59 | 86.03 | 99.9 | 100.0 | 99.8 | 58.5 | 99.8 | 5.5 | 99.9 | 21.3 |
| Secure-aggregation trainer | tau_fed | 0.569546 | 0.693 | 0.721, 0.718, 0.642 | 0.077 | 76.29 | 86.46 | 99.9 | 100.0 | 99.8 | 59.7 | 99.8 | 7.2 | 99.9 | 24.1 |

- On the XGBoost model, false alarms under tau_fed 0.689 % against 0.794 % under tau_C3: lower; recall 76.38 % against 76.82 %. One comparison, not a significance test.
