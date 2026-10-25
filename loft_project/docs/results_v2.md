# FL-DualGuard v2 — results (simulation track)

Run: `results/v2/` (see `manifest.json` for package versions, splits, and
configuration). `manifest.json` records base commit 4843620 with a dirty tree, because
the run was made before this code was committed. The code that produced it is the
commit that adds this file. The only edit after the online run is the figure-scaling and
layout fix in `report.py`, which does not change any numbers. Generated 25 October 2026 on Ubuntu 24.04 (4 CPU cores) with Python 3.12.3.
Methodology: `docs/methodology_v2.md`. Every number below can be regenerated with the
commands in methodology §8.

**Scope of these results.** They come from the LOFT-Bench discrete-time simulator
(bounded OpenFlow tables, reactive install, idle timeouts, 1 s stats polling). They are
not yet confirmed on Mininet/OVS; see §7. Each online condition was run on 10
independent seeds (4000–4009) × 3 domains. Brackets give 95 % bootstrap CIs over
episodes. p-values come from paired Wilcoxon tests on identical traffic, Holm-corrected
(`tables/paired_tests.csv`).

## 1. Sanity: the attack is real and the no-defense baseline is honest

- **Benign-only, no defense:**
  - Peak occupancy (seed 4000): 46 % (D1) and 64 % (D2), plus 75 % during a D3
    flash crowd.
  - No TABLE_FULL events in any of the 30 benign-only episodes.
- **DMS-BTT parameter sets (A1–A3), no defense:**
  - The table overflows 39–108 s after onset.
  - 45–54 % of benign flows are refused admission at least once.
- **Reimplemented DMS-BTT state classifier:**
  - Three-state accuracy is 88–96 % and attack detection rate (ADR) is 92–97 %
    (`offline_dms_state.csv`), the same range as the paper's 86.89 % / 94 %.
  - This supports the reimplementation without proving equivalence.
- **Calibration:**
  - A 1 % benign flag-rate budget fixed on validation runs gave 1.0–1.1 % FPR on
    held-out test runs.

## 2. Offline detection: federation transfers attack knowledge across controllers

Per-entry ROC AUC on offline-test runs, averaged over domains, grouped by whether the
evaluating controller saw the variant in training (`tables/table_offline_by_exposure.csv`,
Fig. 3):

| Detector | Seen locally | Seen only by other controllers | Unseen by all (A6) |
|---|---|---|---|
| DMS-BTT flow classifier (local CatBoost) | 0.995 | 0.884 | 0.620 |
| Local MLP | 1.000 | 0.884 | 0.681 |
| Local SVM-RF (legacy FL-DualGuard) | 1.000 | 0.973 | 0.958 |
| FedAvg MLP | 1.000 | 0.999 | 0.980 |
| **FedProx MLP (FL-DualGuard)** | 1.000 | 0.999 | 0.972 |
| Pooled raw data (oracle) | 1.000 | 1.000 | 0.986 |

At the calibrated threshold, TPR on A6 is 0.57 (FedProx) and 0.68 (FedAvg), compared
with 0.30 (local MLP) and 0.17 (DMS-BTT).

**Communication.** Federation needs 30 rounds × 3 clients with a 2,436-byte model, plus
normalization statistics: **439 KB in total** for the whole training. Validation AUC
reaches 0.999 by about round 15 (Fig. 4).

## 3. Online defense: main comparison (attacked episodes, n = 210 per defense)

`tables/table_main_attack.csv`, Fig. 2:

| Defense | Benign flows impacted (%) | Malicious occupancy after onset (%) | Overflow (s / 300 s) | Decision loop (ms) |
|---|---|---|---|---|
| No defense | 42.27 [40.34, 44.23] | 53.31 | 147.3 | 0.07 |
| OVS evict | 58.78 [56.71, 60.87] | 51.04 | 158.2 | 0.07 |
| Threshold-LRU | 36.24 [34.66, 37.93] | 40.79 | 17.1 | 0.16 |
| DMS-BTT (reimpl.) | 11.96 [9.90, 14.12] | 24.93 | 13.3 | 4.21 |
| Local SVM-RF + DG policy | 8.14 [6.53, 9.94] | 21.87 | 4.3 | 84.36 |
| Local MLP + DG policy | 19.25 [16.83, 21.84] | 25.73 | 4.1 | 2.93 |
| FedAvg + DG policy | 4.65 [3.85, 5.57] | 15.08 | 3.1 | 2.59 |
| **FL-DualGuard (FedProx)** | **5.51 [4.57, 6.57]** | **14.96** | **3.0** | **2.55** |
| Centralized pooled (oracle) | 4.85 [3.97, 5.84] | 13.84 | 2.4 | 2.51 |

**Compared with DMS-BTT**, FL-DualGuard impacts 2.2× fewer benign flows: −6.5 points,
better in 160 of 210 paired episodes, p_Holm < 1e-4. It also leaves 1.7× less malicious
occupancy (200 of 210 wins). On the three DMS-BTT parameter sets and the
fixed-size variants (A1–A3, A5, A7), the two are close (2–5 % vs 4–5 %). The gap
comes from mimicry (A4: 17.7 % vs 41.9 %) and the unseen slow-fill variant
(A6: 3.9 % vs 17.9 %), where DMS-BTT is worse than no defense (12.2 %) because it
evicts benign flows.

**Compared with local learning**, the same policy with a local MLP impacts 19.3 %, which
federation cuts by 3.5×. By exposure group (online):

| Exposure | Local MLP | FL-DualGuard | Pooled oracle |
|---|---|---|---|
| Seen locally | 11.2 % | 4.3 % | 4.1 % |
| Seen only by others | 25.1 % | 6.5 % | 5.4 % |
| Unseen by all (A6) | 12.0 % | 3.9 % | 4.2 % |

**Compared with the oracle**, federation reaches within about 0.7 points of centralized
pooled training without moving any flow records.

**Hardest case.** Mimicry (A4) remains the hardest for every method, including the
oracle (16–18 % benign impact).

## 4. Ablation (`tables/table_ablation.csv`, Fig. 5)

| Variant | Benign impacted (%) | Malicious occ. (%) | Overflow (s) |
|---|---|---|---|
| FL-DualGuard (full) | 5.51 | 14.96 | 3.0 |
| w/o soft demotion (hard delete only) | 8.87 | 28.54 | 9.6 |
| w/o hard overflow guard | **2.44** | 14.45 | 4.7 |
| w/o budget calibration (τ = 0.5) | 5.22 | 16.21 | 3.6 |
| w/o source features | 4.79 | 15.08 | 2.8 |
| w/o context features | **3.75** | **12.96** | 2.2 |

What the ablation shows:

- **Soft demotion is the essential mitigation primitive.** Without it, malicious
  occupancy doubles and overflow time triples (210 of 210 paired wins for the full
  method).
- **Calibration** mainly lowers malicious occupancy (207 of 210 wins). Benign impact
  is comparable either way.
- **Source features** are not needed: the federated detector works without them, which
  matters because spoofing defeats them.

## 5. Negative and mixed findings (report these in the paper)

1. **FedProx did not beat FedAvg.** FedProx was pre-declared as the proposed optimizer,
   but FedAvg impacted fewer benign flows (4.65 % vs 5.51 %; FedProx lost 146 of 210
   pairs, p_Holm < 1e-4). Malicious occupancy was equal (p = 0.09). With three clients
   and moderate heterogeneity, the proximal term gives no measurable benefit.
2. **The hard overflow guard costs more than it saves at the current settings.**
   Removing it lowers benign impact from 5.5 % to 2.4 %, but overflow time rises from
   3.0 s to 4.7 s. The guard trades benign evictions for overflow seconds, and the
   operator should be able to choose that trade-off. Its h_crit/target values were not
   tuned.
3. **Context features (occupancy, install rate, table APIT) hurt.** The detector is
   trained on undefended runs, where attack phases coincide with near-full tables. A
   defended table stays at about 60–80 % occupancy, so these features shift between
   training and deployment. Dropping them improves every metric.
4. **The legacy SVM-RF detector is competitive on benign impact but costly.** It is not
   significantly different from FL-DualGuard on benign impact (8.1 % vs 5.5 %,
   p = 0.65), but leaves more malicious occupancy (21.9 % vs 15.0 %) and its decision
   loop is 33× slower (84 ms mean). Federation still needs a weight-sharing model.
5. **Overheads.**
   - Demotion raises Packet-In volume by 24.9 % relative to no defense, since demoted
     flows reinstall.
   - On benign-only runs, FL-DualGuard demotes 0.52 % of benign flows and rejects
     none.
   - The p99 decision loop is 6.4 ms, well within the 1 s poll interval.

Findings 2 and 3 were observed on **test** data. The configuration must not be changed
based on them and then re-reported on the same seeds. The correct next step is §6.

## 6. Recommended next experiment (pre-declare before running) — done, see §8

Make the following candidate changes, and select among them on **validation seeds
only** with `loftbench.tune`:

- Drop context features.
- Make the hard guard optional, or tune h_crit ∈ {0.9, 0.95, 1.0} on validation.
- Use FedAvg as the optimizer.

Then evaluate the selected configuration once on **fresh** online seeds (e.g. 5000–5009)
and report both runs.

Add robustness checks:

- More controllers (5–10) with Dirichlet-skewed exposure.
- Replay of real benign traces (bigFlows.pcap, CAIDA).
- An adaptive attacker that knows the demotion timeout.

## 7. What is still missing before submission

1. **Emulation confirmation (sudo needed).** Run `testbed/README.md` acceptance runs
   1–4 on Mininet/OVS. Report whether the no-defense overflow and the FL-DualGuard
   occupancy reduction reproduce. This is the largest gap.
2. **DMS-BTT fidelity check.** Check the reimplementation against Section 4 of the
   paper (the PDF was not in the workspace).
3. **Related work.** Cite adaptive and dynamic idle-timeout prior art, and position soft
   demotion relative to it.
4. **Legacy results.** The legacy `results/*.png` and `paper_results_section.md`
   (98 % accuracy on synthetic shortcut data) must not be used.

## 8. v2.1 — validation-selected configuration, one-shot test on fresh seeds

Protocol (`loftbench/v21.py`, artifacts in `results/v21/`):

1. **Pre-registration.** The candidate set, selection rule, and fresh test seeds were
   written to `preregistration.json` and committed (`39e36af`) before any v2.1
   episode ran.
   - **Candidates (24):** detector ∈ {FedProx, FedAvg, FedProx without context
     features, FedAvg without context features} × hard guard ∈ {0.90, 0.95, off} ×
     ρ ∈ {0.5, 0.7}, with t_short = 1 s.
   - **Rule:** minimize benign flows impacted on attacked validation episodes, subject
     to malicious occupancy ≤ 15 %, overflow ≤ 5 s, and benign-only impact ≤ 1 %.
2. **Selection** on validation seeds 2000–2002 only (1,728 episodes,
   `selection_table.csv`). It chose **FedAvg, hard guard off, ρ = 0.7, t_short = 1 s**,
   with validation benign impact 1.92 %, malicious occupancy 14.5 %, and overflow
   4.55 s. The choice was committed (`51df171`) before testing.
3. **One-shot test** on fresh seeds 5000–5009, which no earlier stage touched. The
   script refuses to rerun it. All 7 defenses ran on identical traffic: 210 attacked
   plus 30 benign-only episodes each.

### 8.1 Main result (attacked episodes, n = 210)

| Defense | Benign flows impacted (%) | Malicious occ. (%) | Overflow (s) | Decision p99 (ms) |
|---|---|---|---|---|
| No defense | 42.77 [40.96, 44.61] | 53.45 | 147.4 | 0.7 |
| DMS-BTT (reimpl.) | 12.09 [9.96, 14.28] | 24.93 | 13.3 | 14.3 |
| Local MLP + v2 policy | 19.61 [17.20, 22.11] | 25.89 | 4.2 | 10.8 |
| Local MLP (no ctx) + v2.1 policy | 8.95 [7.13, 10.91] | 20.74 | 24.7 | 10.5 |
| FL-DualGuard v2 | 5.91 [4.96, 6.94] | 14.97 | 3.2 | 9.9 |
| **FL-DualGuard v2.1** | **2.24 [1.99, 2.51]** | **14.43** | **4.9** | **7.5** |
| Pooled oracle (v2 policy) | 5.30 [4.37, 6.30] | 13.93 | 2.5 | 8.1 |

Paired Wilcoxon tests, Holm-corrected (`results/v21/tables/paired_tests.csv`), for
benign flows impacted:

| v2.1 vs | Mean difference | Paired wins / losses | p_Holm |
|---|---|---|---|
| DMS-BTT | −9.9 points (5.4× fewer) | 160 / 50 | < 1e-4 |
| Local no-ctx, same policy | −6.7 points (4.0× fewer) | 183 / 27 | < 1e-4 |
| v2 | −3.7 points | 210 / 0 | < 1e-4 |

**The federation effect under identical policy and features** is the v2.1 versus
local no-ctx row: 2.24 % vs 8.95 % benign impact. Local training also leaves overflow
at 24.7 s against 4.9 s, because local detectors miss variants seen only elsewhere.
The occupancy difference against local no-ctx is not significant by paired test
(p = 0.78). Its mean gap of −6.3 points comes from a minority of episodes where
local detectors fail badly, so report the means *and* the paired counts.

**Per variant** (benign impacted %, `table_test_by_variant.csv`, Fig. 7):

| Defense | A1 | A2 | A3 | A4 | A5 | A6 (unseen) | A7 |
|---|---|---|---|---|---|---|---|
| DMS-BTT | 4.9 | 5.1 | 5.1 | 42.2 | 4.9 | 18.1 | 4.3 |
| v2 | 4.6 | 2.5 | 4.7 | 17.8 | 4.1 | 5.5 | 2.4 |
| **v2.1** | **2.0** | **1.9** | **2.1** | **3.9** | **2.0** | **1.9** | **1.9** |

Mimicry (A4), the hardest case in v2, falls from 17.8 % to 3.9 %. Most of the v2
damage on A4 came from the hard guard evicting benign entries.

### 8.2 Costs and caveats

- **Overflow time rises.** It goes from 3.2 s (v2) to 4.9 s (v2.1), losing 177 of 210
  pairs, p_Holm < 1e-4. This is the declared trade-off of dropping the hard guard, and
  it is within the pre-registered 5 s limit. v2.1 is still 8.4 s better than DMS-BTT.
- **The comparison with the pooled oracle is not like-for-like.** The oracle row uses
  the v2 policy, so "v2.1 beats pooled" must not be claimed. A pooled model under the
  v2.1 policy was not part of the pre-registered test set.
- **Benign-only cost.** v2.1 demotes 0.45 % of benign flows on benign-only seeds, with
  no rejections. One fresh D3 benign-only seed shows 0.07 s of overflow under *every*
  defense, from a flash crowd that briefly reaches capacity.
- **Packet-In** is +23.7 % relative to no defense, about the same as v2.
- **Testbed.** The v2.1 model is exported for the testbed as
  `results/v21/exported/v21_<D>.json`. It reproduces the Python model exactly (max
  difference 0), and `run_testbed.py` now uses it by default.

### 8.3 What the paper should claim

FL-DualGuard v2.1 is the proposed configuration, and v2 serves as the pre-declared
first design, with its ablation evidence. The claims supported in simulation:

1. Federated detectors with soft demotion reduce benign disruption by 5.4× relative
   to a DMS-BTT reimplementation, and by 4× relative to local training under the
   identical policy.
2. The gain is largest on mimicry and never-seen variants.
3. These claims hold on a pre-registered, one-shot test.

Emulation confirmation (§7.1) remains the main open item.
