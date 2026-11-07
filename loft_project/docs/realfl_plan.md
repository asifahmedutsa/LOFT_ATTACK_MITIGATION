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

**Amended 8 November, after the benign-only calibration and before any attack run.** univ2 is a
much lighter network: at 6,000 pps its parts hold 716-835 entries against T1A's 1,681, and matching
T1A would mean replaying univ2 faster than it was captured. Each univ2 part is therefore replayed
at its own captured rate (pt0 11,178 pps, pt3 10,226 pps, pt6 9,246 pps), holding 1,370, 1,149 and
1,025 entries; the networks differ in load, as real networks do.

## Data

- Training rows: each controller's own network, its attacks and benign only, seeds 1000-1004
  (labelled rule rows as in loftbench.data.collect_run).
- Thresholds: benign rows of the network where the detector is used, seeds 2000-2002.
- Test rows: T1B and UH, all eight attacks (A1-A7, E9P) and benign, seeds 3000-3002. T1B is
  replayed at the testbed's 600 pps, as in every earlier T1B test (at 1,200 pps one pass is 172 s).

## Detectors compared

| Detector | Training | Eligible as FEVER's detector |
|---|---|---|
| Local only | C3's own model (the no-sharing ablation) | no (ablation) |
| One-shot sharing | C1-C3 CatBoost models, mean probability (current FEVER design) | yes |
| Federated XGBoost | Flower, bagging, 100 rounds of one tree per client (300 trees, as the central XGBoost), server plus 3 client processes | yes |
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

**Amended 8 November, before any evaluation.** The first federated XGBoost run used 20 rounds of
5 trees per client; Flower's FedXgbBagging keeps only one new tree per client per round, so that
model held 64 trees instead of 300. It is rerun as 100 rounds of one tree per client. No result of
either run was looked at before this change.

## Added 8 November, after the results above: lossless federated XGBoost

*Written and committed before this detector was coded, trained or evaluated. It is proposed after
seeing that no federated detector carried Mimic (A4) to T1B while pooled training did, so it is
reported as an added test, not part of the original comparison.*

Detector: histogram-based federated XGBoost. Three worker processes, one per controller, each
loading only its own rows (results/realfl/fl_data/C*.npz). They agree the feature bins by merging
quantile sketches; for every tree node each worker sends only the sums of gradients and hessians
per feature bin, the sums are added (allreduce) and every worker picks the same split. No rows,
labels or per-row values leave a worker. This is XGBoost's own distributed hist algorithm
(xgboost.collective with RabitTracker, the scheme of NVIDIA FLARE's histogram-based federated
XGBoost); it trains the same model as pooled XGBoost. Settings as pooled XGBoost: 300 trees,
depth 6, learning rate 0.1, hist.

Rule (same measures, thresholds and test rows as above):
1. It replaces federated XGBoost (bagging) as FEVER's detector if its T1B score is at least
   2 points above the bagging model's (37.31) and its T1B benign false-alarm rate is at most 0.2 %.
2. Otherwise federated XGBoost (bagging) stays FEVER's detector.
Also reported: its agreement with pooled XGBoost (mean absolute probability difference on the T1B
test rows), and the bytes exchanged per tree.

## Added 8 November: confirmation of the lossless model, and its deployment

*Written and committed before any of the data below was collected or any model below trained.
The first lossless result (section above) was chosen and reported on test seeds 3000-3002 and
under a rule written after the pooled result was known; it is therefore treated as exploratory,
and this section is the confirmatory test.*

### Design
- **Fresh test seeds 3003-3005** (T1B at 600 pps and UH, all eight attacks and benign). Seeds
  3000-3002 are not used again. Thresholds as before (0.1 % of the network's benign rows, 2000-2002).
- **Three training replicates**, each with its own training seeds: R0 = 1000-1004 (the existing
  data), R1 = 1005-1009, R2 = 1010-1014. Model seed = replicate number. (XGBoost without
  subsampling is deterministic given its data, so replicates differ by data, not only by seed.)
- **Three attack placements** on the same three networks, so the result does not hinge on which
  controller saw which attack:

  | Placement | C1 (univ2 pt0) | C2 (univ2 pt3) | C3 (bigFlows T1A) |
  |---|---|---|---|
  | P1 (as before) | A1, A4 | A2, A5 | A3, A7 |
  | P2 | A2, A5 | A3, A7 | A1, A4 |
  | P3 | A3, A7 | A1, A4 | A2, A5 |

  A6 and E9P stay unseen. On T1B, "seen locally" is C3's pair and "seen only by another
  controller" is the other four, per placement.
- 9 training sets (3 placements x 3 replicates). On each: local only (C3), one-shot sharing
  (CatBoost), pooled XGBoost, federated XGBoost bagging (Flower, 100 x 1 tree), FedProx (Flower),
  lossless federated XGBoost. Same settings as above.

### Hypotheses (T1B, fresh test seeds; score as above)
- H1: lossless score >= bagging score + 2 points.
- H2: lossless T1B benign false-alarm rate <= 0.2 %.
- The lossless model stays FEVER's detector if H1 and H2 both hold in at least 8 of the 9 sets;
  otherwise federated XGBoost (bagging) becomes FEVER's detector again.
- Reported, not tested: lossless minus pooled XGBoost score; per-attack recall (mean and range
  over the 9 sets); UH results, including FedProx's recall on E9P, whatever they show.

### Robustness and cost
- Dropped controller: lossless training with a checkpoint every 50 trees; one worker is killed
  after the checkpoint at 150 trees, all workers restart from it. Passes if the final model's
  probabilities match the uninterrupted model within 1e-6 on the T1B test rows.
- Traffic: loopback bytes during training minus the idle loopback rate measured over 30 s just
  before; reported with the analytic histogram size.

### Deployment (testbed controller), development seeds only
- The deployed detector is the lossless model of P1 / R0 (results/realfl/fedxgb_hist.json),
  exported to the controller's tree JSON (loftbench/treejson.py, parity < 1e-4).
- tau: 0.1 % of T1A benign rows, seeds 2000-2002 (as for every detector above).
- Check (simulator, T1B at 600 pps, seeds 2000-2002, as the v6 check): FEVER with the new
  detector against FEVER v6 (CatBoost), all other settings unchanged. Passes if for A2, A4 and
  E9P harm <= v6 + 0.1 points and attack occupancy <= v6 + 2 points, no benign host is blocked,
  and benign-only harm <= 0.1 %.
- If it fails: rule A re-tuned on the same seeds over n_min {30, 50, 80} x frac_min {0.1, 0.2,
  0.3}; the passing setting with the lowest mean attack occupancy is kept. If none passes, the
  testbed keeps the v6 detector and the federated model is reported offline only.
- Final confirmation of the whole system is the testbed campaign on seeds 4160-4162.
