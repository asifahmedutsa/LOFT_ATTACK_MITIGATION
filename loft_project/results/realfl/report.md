# FEVER's detector on real traffic: results (8 November 2026)

Plan and choice rule: docs/realfl_plan.md (fixed before any data). Controllers C1 univ2 part 0 (G1, Mimic), C2 univ2 part 3 (G2, Spoof), C3 bigFlows T1A (G3, Pulse); Slow and Aware seen by no one. Test networks: T1B (bigFlows, later part; C3's own network) and UH (univ2 part 6, no controller). Recall (%) at the threshold that flags 0.1 % of the network's own benign rows; test seeds 3000-3002.

## Federated training (Flower 1.20, one server and three client processes over gRPC)

- Federated XGBoost (bagging): 100 rounds, 3 clients per round, 0 failures, 0.80 MB sent by the clients in total, final model 689 kB (300 trees).
- FedProx (neural network, mu 0.01): 30 rounds, 3 clients per round, model 2436 bytes.
- Cyclic federated XGBoost (exploratory, not in the choice rule): 100 rounds, one client per round, 300 trees.

## By exposure

| Detector | Seen locally | Seen only by another controller | Seen by no one | Benign false alarms (%) |
|---|---|---|---|---|
| Local only (C3) | 100.0 | 74.6 | 0.1 | 0.1 |
| One-shot sharing (CatBoost) | 100.0 | 74.2 | 0.0 | 0.0 |
| One-shot sharing (XGBoost) | 100.0 | 74.2 | 0.0 | 0.0 |
| Pooled (CatBoost) | 100.0 | 99.2 | 17.9 | 0.2 |
| Pooled (XGBoost) | 100.0 | 99.3 | 18.4 | 0.0 |
| Federated XGBoost (Flower) | 100.0 | 74.6 | 0.0 | 0.0 |
| Cyclic federated XGBoost (exploratory) | 100.0 | 75.5 | 1.0 | 0.0 |
| FedProx (Flower) | 93.4 | 74.4 | 4.3 | 0.0 |

| Detector | Seen by some controller | Seen by no one | Benign false alarms (%) |
|---|---|---|---|
| Local only (C3) | 82.8 | 0.0 | 0.1 |
| One-shot sharing (CatBoost) | 99.8 | 24.6 | 0.1 |
| One-shot sharing (XGBoost) | 98.9 | 15.3 | 0.2 |
| Pooled (CatBoost) | 99.8 | 22.1 | 0.1 |
| Pooled (XGBoost) | 99.7 | 21.0 | 0.1 |
| Federated XGBoost (Flower) | 99.6 | 17.0 | 0.2 |
| Cyclic federated XGBoost (exploratory) | 99.7 | 21.8 | 0.1 |
| FedProx (Flower) | 96.3 | 67.1 | 0.1 |

## Per attack

### T1B (bigFlows)

| Detector | G1 | G2 | G3 | Mimic | Spoof | Slow | Pulse | Aware |
|---|---|---|---|---|---|---|---|---|
| Local only (C3) | 100.0 | 99.7 | 100.0 | 0.2 | 100.0 | 0.6 | 100.0 | 0.0 |
| One-shot sharing (CatBoost) | 99.7 | 99.0 | 100.0 | 0.0 | 99.7 | 0.0 | 100.0 | 0.0 |
| One-shot sharing (XGBoost) | 99.7 | 99.0 | 100.0 | 0.0 | 100.0 | 0.0 | 100.0 | 0.0 |
| Pooled (CatBoost) | 100.0 | 100.0 | 100.0 | 96.9 | 100.0 | 71.2 | 100.0 | 1.2 |
| Pooled (XGBoost) | 100.0 | 100.0 | 100.0 | 97.4 | 100.0 | 70.4 | 100.0 | 2.1 |
| Federated XGBoost (Flower) | 99.8 | 100.0 | 100.0 | 0.4 | 99.9 | 0.1 | 100.0 | 0.0 |
| Cyclic federated XGBoost (exploratory) | 99.8 | 100.0 | 100.0 | 3.8 | 99.9 | 4.1 | 100.0 | 0.0 |
| FedProx (Flower) | 87.5 | 96.0 | 93.1 | 27.4 | 87.3 | 7.9 | 94.0 | 3.2 |

### UH (held-out univ2)

| Detector | G1 | G2 | G3 | Mimic | Spoof | Slow | Pulse | Aware |
|---|---|---|---|---|---|---|---|---|
| Local only (C3) | 100.0 | 99.7 | 100.0 | 0.0 | 100.0 | 0.1 | 100.0 | 0.0 |
| One-shot sharing (CatBoost) | 100.0 | 100.0 | 100.0 | 98.7 | 100.0 | 89.3 | 100.0 | 3.2 |
| One-shot sharing (XGBoost) | 100.0 | 100.0 | 100.0 | 93.5 | 100.0 | 61.2 | 100.0 | 0.1 |
| Pooled (CatBoost) | 100.0 | 100.0 | 100.0 | 98.7 | 100.0 | 83.9 | 100.0 | 1.6 |
| Pooled (XGBoost) | 100.0 | 100.0 | 100.0 | 98.5 | 100.0 | 78.7 | 100.0 | 1.9 |
| Federated XGBoost (Flower) | 100.0 | 100.0 | 100.0 | 97.9 | 100.0 | 66.8 | 100.0 | 0.5 |
| Cyclic federated XGBoost (exploratory) | 100.0 | 100.0 | 100.0 | 98.1 | 100.0 | 86.6 | 100.0 | 0.4 |
| FedProx (Flower) | 98.2 | 99.5 | 99.0 | 83.7 | 98.6 | 68.1 | 99.2 | 66.8 |

## Choice (rule fixed in advance)

Scores on T1B (mean of 'seen only by another controller' and 'seen by no one'): Local only (C3) 37.35, One-shot sharing (CatBoost) 37.09, One-shot sharing (XGBoost) 37.12, Pooled (CatBoost) 58.59, Pooled (XGBoost) 58.88, Federated XGBoost (Flower) 37.31, Cyclic federated XGBoost (exploratory) 38.22, FedProx (Flower) 39.34.

**FEVER's detector: Federated XGBoost (Flower) (rule 1).**

## Reading

- Standard attacks (G1, G2, G3, Spoof, Pulse) are caught by every detector, also by C3's own model alone: they look alike.
- Sharing matters on the held-out network UH: C3's own model catches Mimic 0.0 % there, every shared model 94-99 %.
- On bigFlows, Mimic learned on univ2 does not transfer through any federated method (0-27 %); only pooled training (all rows in one model, no privacy) catches it (97 %). Disguised traffic is network-specific; the volume rule, which uses no detector, is what stops it on the testbed.
- Aware is missed by every tree model on both networks (0-3 %); FedProx catches it on UH (67 %) but not on bigFlows.
- Federated XGBoost matches one-shot sharing (within 0.3 points) and is real multi-round FL, so it replaces it as FEVER's detector by the rule fixed in advance.
- Not tested yet: lossless (histogram-based) federated XGBoost, which trains as pooled XGBoost does and could close the Mimic gap on bigFlows; it would need its own rule fixed before running.
