# FEVER on real traffic: federated training and the detector choice

*Fixed 8 November 2026, before any data was collected or any model trained.*

## Networks (all real traffic, replayed in the simulator)

| Controller | Traffic | Attacks it trains on |
|---|---|---|
| C1 | univ2 part 0 (first 3,000,000 packets) | A1 (G1), A4 (Mimic) |
| C2 | univ2 part 3 (first 3,000,000 packets) | A2 (G2), A5 (Spoof) |
| C3 | bigFlows T1A (first 40 %), the test network's own controller | A3 (G3), A7 (Pulse) |
| Held-out network UH | univ2 part 6 (first 3,000,000 packets), no controller trains on it | none |

A6 (Slow) and E9P (Aware) are trained on by no one.
The univ2 replay rate is set, before any attack run, so that its benign-only table occupancy
(mean entries over 60-240 s, seeds 2000-2002) is within 15 % of T1A at 1,200 pps.

## Data

- Training rows: each controller's own network, its attacks and benign only, seeds 1000-1004
  (labelled rule rows as in loftbench.data.collect_run).
- Thresholds: benign rows of the network where the detector is used, seeds 2000-2002.
- Test rows: T1B and UH, all eight attacks (A1-A7, E9P) and benign, seeds 3000-3002.

## Detectors compared

| Detector | Training | Eligible as FEVER's detector |
|---|---|---|
| Local only | C3's own model (the no-sharing ablation) | no (ablation) |
| One-shot sharing | C1-C3 CatBoost models, mean probability (current FEVER design) | yes |
| Federated XGBoost | Flower, bagging, 20 rounds, server plus 3 client processes | yes |
| FedProx | Flower, neural network (our FL-DualGuard MLP), 30 rounds | yes |
| Pooled | One CatBoost on all controllers' rows (no privacy; upper bound) | no (reference) |

## Measures (on T1B, from C3's point of view; and on UH)

Recall at the threshold that flags 0.1 % of the network's own benign rows (seeds 2000-2002), on
- seen locally (T1B only): A3, A7;
- seen only by another controller: A1, A2, A4, A5;
- seen by no one: A6, E9P;
plus precision, F1 and the benign false-alarm rate on the test seeds.

## Choice rule

Score = mean of (recall seen only by another controller, recall seen by no one) on T1B.
1. Federated XGBoost becomes FEVER's detector if its score is at least the one-shot score minus
   1 point and its T1B benign false-alarm rate is at most 0.2 %.
2. Otherwise FedProx, under the same conditions, if its score is at least 2 points above both.
3. Otherwise one-shot sharing stays FEVER's detector, and the federated results are reported as
   the comparison.
UH results are reported but do not enter the choice.
