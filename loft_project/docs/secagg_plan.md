# Secure aggregation and a federated threshold for FEVER's detector: plan and preregistration

Drafted 14 November 2026; approved by the user and fixed at commit on 17 November 2026, before any
code below was written or run on the test rows. A follow-up study after the final campaign
(docs/final_campaign_prereg.md). It changes nothing in the campaign's results.

## 1. Why

- FEVER's lossless federated XGBoost (fl/run_fedxgb_hist.py) sends each controller's per-bin
  gradient and hessian sums in the clear through XGBoost's allreduce. The other controllers and the
  tracker see them, and a reviewer can ask what these histograms reveal.
- The detector's threshold is set on C3's benign rows of one trace (T1A, 0.1 % budget). On T1B's
  benign test rows its false alarms are 0.79 %, eight times the budget (results/tbfl/report.md).

## 2. Secure aggregation of the histograms

**Why a separate trainer.** The pip build of XGBoost 3.4.1 has no hook in its allreduce: its federated
plugin needs a source build and a C++ processor, as NVFlare does. Instead, a small histogram
gradient-boosting trainer (fl/secagg_xgb.py) in which every message between controllers is explicit:

- The same model as FEVER's: binary logistic loss, 300 trees, depth 6, eta 0.1, lambda 1,
  min_child_weight 1, gamma 0, 256 bins per feature, on the controllers' rows in results/tbfl/fl_data.
- **Bins.** Each controller counts its values on a fixed public grid per feature (4,096 cells over the
  feature's documented range, log-spaced for counts and durations). The counts are aggregated securely,
  and every controller takes the same 256 quantile cuts from the sum. No controller's sketch is sent.
- **Trees.** For each node every controller computes its gradient and hessian sums per bin. The sums
  are aggregated securely, and every controller chooses the same split and leaf values from them. The
  base score comes from securely aggregated label and row counts.

**Masking.** Pairwise additive masks (Bonawitz et al., CCS 2017, without dropout recovery):

- Each pair of controllers agrees on a key once by X25519 (the cryptography package).
- For every message, each controller encodes its sums in fixed point (64-bit integers, scale 2^40,
  modulo 2^64). It adds, for every other controller, a mask from ChaCha20 keyed by the pair key and the
  message number, with the sign set by the pair's order.
- The aggregator adds the three masked vectors. The masks cancel, leaving the exact fixed-point sum.
- A dropped controller stops the round, and training restarts from the last tree (as the
  dropped-controller test does now).

**What it protects, and what it does not.**

- Under honest-but-curious controllers and aggregator, no party sees another controller's histograms.
- The sum over the three controllers is revealed, because every controller needs it to choose splits.
- With three controllers, two that collude can subtract their own sums and learn the third's.
- No differential privacy is added.

**Unmasked control.** The same trainer, same fixed-point path, masks set to zero.

## 3. Federated threshold

- Each controller scores its own benign calibration rows with the federated model:
  - C1: U1t benign seeds 4190–4192;
  - C2: U2t benign seed 4190;
  - C3: T1A benign seeds 4173–4175.

  None of these runs is in training.
- Each controller counts its scores on a fixed grid (10,000 cells in log-odds). The counts are
  aggregated securely, as in section 2.
- tau_fed is the smallest grid edge at which the pooled false-alarm rate is at most 0.1 %.
- Compared with:
  - tau_C3, the current rule (C3's T1A benign rows only, as deployed);
  - tau_max, the largest of the three controllers' local thresholds. It needs no secure aggregation,
    but each controller's threshold is revealed.

## 4. Measures

All on the T1B test rows (seeds 4176–4178), as in Table 5.

- **Exactness:** whether the masked and unmasked runs give the same trees (split feature, cut,
  default direction and leaf value, bit for bit) and the same scores on every test row.
- **Fidelity to XGBoost:** the trainer's accuracy, precision, recall, F1 and false alarms against
  fedxgb_hist.json, at the same threshold rule, and the share of test rows on which the two agree.
- **Cost:** bytes sent (payload and on the loopback interface), training time, and the time spent
  masking. Masked against unmasked, and against fl/run_fedxgb_hist.py.
- **Threshold:** false alarms on T1B benign test rows, and recall overall and per attack. Given for
  tau_C3, tau_fed and tau_max, on the XGBoost model and on the trainer's model. False alarms are also
  given on UHt benign seed 4190.

## 5. What is run

- Offline only, on this machine:
  - the masked and unmasked runs (three worker processes and an aggregator on loopback);
  - the scoring;
  - one rerun of each with seed 1, to check that the result does not depend on the seed.
- No testbed run in this study. A testbed check of tau_fed (FEVER on T1B G2, Mimic and Aware, seeds
  4160–4164) is a separate decision, after these results.

## 6. Preregistration (fixed at commit)

- **S1 (exactness).** The masked and unmasked runs give identical trees and identical scores on every
  T1B test row. Pass or fail.
- **S2 (fidelity).** The trainer's F1 and recall on the T1B test rows are within 1.0 point of
  fedxgb_hist.json at the same threshold rule, and the two agree on at least 99 % of test rows.
  Pass or fail per condition.
- **S3 (cost).** Reported, not tested. Expected: masked bytes within 5 % of unmasked bytes, and
  masked time within 25 % of unmasked time.
- **T1 (threshold).** On T1B benign test rows, false alarms under tau_fed are lower than under tau_C3.
  This is one comparison on the XGBoost model, so no test across seeds. With only three benign test
  runs, it is reported as the measured rates with each seed's rate beside them, plus the recall cost.
  It is not a significance test.
- Nothing else is a claim. Any further analysis is labelled exploratory.

## 7. Files

- fl/secagg_xgb.py: trainer, masking, workers and aggregator; writes the model and log.
- loftbench/secagg_eval.py: scoring, thresholds, tables.
- tests/test_secagg.py:
  - the masks cancel exactly;
  - masked equals unmasked on a small synthetic set;
  - on a small set the trainer gives XGBoost's splits.
- results/secagg/: models, logs, report.md.
- testbed/fig_final.py: a federation-cost row for the secure version, and a threshold table.
