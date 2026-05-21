# Methodology: FL-DualGuard (This Repo) vs DMS-BTT (Paper)

## 1) Purpose

This document explains:
- how **our approach** (FL-DualGuard in this repository) works,
- how **DMS-BTT** works in the paper,
- how to run a safer, auditable evaluation pipeline,
- how to execute each stage step-by-step.

## 2) Our Approach (FL-DualGuard)

### 2.1 Core idea

FL-DualGuard is a binary detection pipeline (`normal` vs `attack`) using:
- packet/flow-level engineered features,
- local controller training,
- federated-style aggregation flow,
- SVM + RandomForest soft-voting classifier.

### 2.2 Current repository components

- Data generation: `loft_project/data/generate_realistic_dataset.py`
- Local model training: `loft_project/models/local_model_trainer.py`
- Federated client/server scripts:
  - `loft_project/federated/fl_client.py`
  - `loft_project/federated/fl_server.py`
- Audited evaluation (new):
  - `loft_project/eval/run_audited_eval.py`

### 2.3 Important integrity update

`loft_project/results/generate_final_results.py` is now blocked by default because it contains demo/hardcoded reporting logic.

If you really want to run it for demo-only figures (not for claims), use:

```bash
ALLOW_DEMO_RESULTS=1 python loft_project/results/generate_final_results.py
```

## 3) DMS-BTT Approach (Paper)

### 3.1 Core idea

DMS-BTT is a two-level threshold SDN defense system:
- detects LFTO attack state with CatBoost using `(FN, APIT)`,
- identifies malicious flows with CatBoost using `(Numb, PIT, Sizep)`,
- mitigation behavior changes based on threshold urgency:
  - `DET_H2 = 75%` of table: start detection mode,
  - `DET_H1 = 90%` of table: start overflow prevention mode.

### 3.2 Evaluation style used by DMS-BTT

- Mininet + Ryu + OVS online simulation environment,
- flow table size 3500, idle timeout 10 seconds,
- 3 LFTO parameter groups, 5:1 train:test split (offline experiments),
- online comparison (600s) using mitigation metrics:
  - average/max `Pa`,
  - flow table usage,
  - earliest overflow time,
  - Packet-In, Table-Full messages,
  - CPU usage.

## 4) Fair Comparison Methodology

To compare fairly, do **not** compare only one accuracy number.
Use two layers:

1. **Offline classifier quality** (accuracy, precision, recall, F1, AUC)
2. **Online mitigation behavior** (Pa, overflow, control-plane load)

This repository now includes the audited offline entrypoint.  
For full DMS-BTT parity, online Mininet harness must be added and executed under the same topology/attack settings.

## 5) Step-by-Step Execution

## 5.1 Setup

From repository root:

```bash
cd /Users/towhid/PC/Research/LOFT/LOFT_ATTACK_MITIGATION
python -m pip install -U pandas numpy scikit-learn matplotlib scipy
```

## 5.2 Generate dataset

```bash
python loft_project/data/generate_realistic_dataset.py
```

Expected output dataset:
- `loft_project/data/full_dataset.csv`

## 5.3 Train local controller models

```bash
python loft_project/models/local_model_trainer.py
```

Expected artifacts:
- `loft_project/models/saved/controller_1_model.pkl`
- `loft_project/models/saved/controller_2_model.pkl`
- `loft_project/models/saved/controller_3_model.pkl`
- corresponding scaler and metrics files.

## 5.4 Run audited offline evaluation (recommended for reporting)

Default (drops leakage-prone `spoofing_conf`):

```bash
python loft_project/eval/run_audited_eval.py
```

Optional (include leakage-prone feature, not recommended for claims):

```bash
python loft_project/eval/run_audited_eval.py --allow-leakage-prone-feature
```

Expected audited artifacts:
- `loft_project/results/audited/metrics.json`
- `loft_project/results/audited/manifest.json`
- `loft_project/results/audited/predictions.csv`
- `loft_project/results/audited/roc_points.csv`
- `loft_project/results/audited/confusion_matrix.csv`
- `loft_project/results/audited/train_indices.csv`
- `loft_project/results/audited/test_indices.csv`

## 5.5 (Optional) Run federated scripts

Terminal 1:

```bash
python loft_project/federated/fl_server.py
```

Terminal 2:

```bash
python loft_project/federated/fl_client.py 1
```

Terminal 3:

```bash
python loft_project/federated/fl_client.py 2
```

Terminal 4:

```bash
python loft_project/federated/fl_client.py 3
```

## 5.6 (Optional) Demo-only table generator

This is blocked unless explicitly enabled:

```bash
ALLOW_DEMO_RESULTS=1 python loft_project/results/generate_final_results.py
```

Do not use this output as final scientific evidence.

## 5.7 DMS-BTT-aligned comparison execution checklist

For full parity with DMS-BTT methodology:

1. Create Mininet topology with paper-equivalent constraints.
2. Replay background traffic with `tcpreplay` at target packet rate.
3. Implement LFTO parameter sets from paper Table 2.
4. Collect:
   - flow-table state snapshots for `(FN, APIT)`,
   - per-flow features `(Numb, PIT, Sizep)`.
5. Train/evaluate with 5:1 split for offline modules.
6. Run 600s online mitigation runs and report paper-aligned metrics.

## 5.8 Run DMS-BTT-style offline CatBoost baseline (new scaffold)

If you already prepared two CSV files:
- state CSV with `FN`, `APIT`, and optional `state_label`,
- flow CSV with `Numb`, `PIT`, `Sizep`, `label`,

run:

```bash
python -m pip install catboost
python loft_project/eval/run_dms_btt_offline_baseline.py \
  --state-csv path/to/state_dataset.csv \
  --flow-csv path/to/flow_dataset.csv
```

Expected output:
- `loft_project/results/dms_btt/offline/dms_btt_offline_metrics.json`

## 6) Reporting Guidance

When reporting performance:
- cite `loft_project/results/audited/metrics.json` as primary source,
- include `manifest.json` to show seed/split/features/commit,
- explicitly state whether leakage-prone features were excluded,
- keep DMS-BTT comparisons limited to equivalent protocols and metrics.

