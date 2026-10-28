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

Emulation confirmation (§7.1) remains the main open item. An independent review
(§9) qualifies claims 1–3; read it before using them.

## 9. Independent review findings (26 October 2026)

A critical review of the v2/v2.1 artifacts. Two probes were added and run on fresh
test seeds. They report only and change no configuration:
`loftbench/probe_harm.py` and `loftbench/probe_adaptive.py`, with outputs in
`results/review/`.

### 9.1 What was verified

- Every §8.1 number recomputes from `results/v21/test_episodes.csv`.
- `preregistration.json` matches `preregistration.sha256`. After the test, the only
  changes to `v21.py` are the export and figure code; selection and test logic are
  unchanged.
- The exported v2.1 model matches the Python model (max difference 0, identical τ).
- **Clustering does not change significance.** The 210 attacked episodes share benign
  traffic across the 7 variants of each (domain, seed), so they are not independent.
  Averaging within the 30 (domain, seed) clusters, v2.1 still wins 30/30 against
  every comparator (Wilcoxon p ≈ 2e-9).

### 9.2 Problems, most serious first

1. **An adaptive attacker defeats soft demotion.** Demotion removes a flow only if
   its refresh gap exceeds t_short = 1 s. Every variant A1–A7 refreshes every
   5–10 s. Attackers that refresh every 0.8–0.95 s use about 8× the packet rate
   (3.8k–7.5k pps). This is still small against a 250 Mbps link.

   `probe_adaptive.csv`: 3 seeds × 3 domains, means.

   | Variant | Defense | Benign impacted (%) | Malicious occ. (%) | Overflow (s) |
   |---|---|---|---|---|
   | fast-refresh (3.8k pps) | No defense | 78.8 | 86.9 | 240.4 |
   | | DMS-BTT | 75.6 | 84.8 | 160.5 |
   | | v2.1 | 75.4 | 84.7 | 203.1 |
   | fast-mimic (7.5k pps) | No defense | 79.6 | 88.8 | 240.4 |
   | | DMS-BTT | 79.2 | 88.3 | 169.8 |
   | | v2.1 | 79.4 | 87.1 | 215.7 |

   DMS-BTT fails too, so the relative claim survives. However, the claim that
   demotion "defeats the low-rate premise" holds only for attackers slower than
   t_short. The paper needs a bounded threat model and an occupancy-versus-attacker
   packet-budget curve.

2. **"Benign flows impacted" overstates harm.** The metric counts a benign flow
   once its entry is deleted or demoted, even if the flow never sends again.

   `probe_harm.csv`: A1/A4/A6 × 3 domains × 2 seeds. Only 44 % (DMS-BTT), 55 % (v2)
   and 49 % (v2.1) of the benign flows acted on had any later packet. The rest were
   stale entries, and removing them cost nothing.

   "Rejected" flows are still forwarded through the controller slow path. No goodput
   or latency is measured. The ranking is unaffected, but the absolute numbers are
   proxies, not lost service. For example, "42.8 % with no defense" should be
   worded as admission failures.

3. **The one-shot test is weaker than "pre-registered" suggests.** The v2.1
   candidate set was designed from v2 *test-set* ablations (§5). The fresh seeds are
   new draws from the same generator, so design knowledge from the test set carries
   over.

   The pre-registration, selection and test commits are self-authored and 50 minutes
   apart. The rerun guard only checks whether a file exists. Describe it as "design
   informed by an earlier test run; seeds fresh", not as independent confirmation.

4. **The DMS-BTT baseline is disadvantaged.**
   - DualGuard's knobs were tuned on validation (9 policy settings, then
     24 candidates); DMS-BTT's H1/H2 = 0.90/0.75 were not tuned.
   - DMS-BTT has no memory: a deleted attack flow reinstalls with the full 10 s
     timeout on its next refresh, while DualGuard remembers demoted flows.
   - `Numb` is computed from the byte count (`features.py`, the `dms` matrix). Check
     against the paper whether it should be the packet count.
   - An ADR "in the paper's range" from simulated data does not establish fidelity.
   - The 5.4× gap is concentrated in A4 and A6. On A1–A3, A5 and A7 it is
     4.88 % vs 1.97 % (2.5×).

5. **The federation gain is a training-coverage effect by construction.** Each
   domain trains on only 2 of the 7 variants, so local models miss the others.
   - No pooled model was run under the v2.1 policy.
   - A6 recombines existing traits: A4's benign sizes, A5's spoofing, and slower
     timing.
   - The missing comparator is a local model trained on a shared public library of
     attack variants. If it matches federation, the contribution is attack coverage,
     not federated learning.

6. **The 1 % budget is per entry-poll, not per flow.** τ is calibrated on sampled
   (entry, poll) rows. A benign flow is scored at every poll while installed, so its
   chance of being flagged at some point is higher.
   - With ρ = 0.5, benign-only impact is 3.7 % (`results/v21/selection_table.csv`).
   - v2.1's 0.45 % benign-only cost comes mainly from the ρ = 0.7 gate: benign-only
     occupancy peaks at 46–64 % in D1/D2, so the policy rarely acts there.

7. **The overflow limit is met only on the mean.**
   - 41 % of v2.1 attacked episodes exceed 5 s of overflow (maximum 27.7 s).
   - The CI [4.25, 5.60] straddles the limit.
   - On A4, v2.1 averages 12.5 s of overflow and 22 % malicious occupancy, above the
     15 % limit.

8. **Results vary by domain and are simulation-only.**
   - v2.1 impacts 0.58 % (D1), 4.00 % (D2) and 2.13 % (D3) of benign flows; report
     per domain.
   - Decision-loop times are Python timings inside the simulator.
   - The exported τ was calibrated on simulated benign traffic and will need
     recalibration on Mininet traffic.

### 9.3 What to change before submission

- Add the adaptive attacker (refresh gap ≤ t_short) to the threat-model section and
  report its result.
- Report goodput/latency on the testbed, and count only harm to flows that are still
  active.
- Tune DMS-BTT's thresholds on the same validation budget, and give it a
  blocklist/memory variant.
- Add a "local + shared attack library" comparator, and a pooled model under the
  v2.1 policy.
- State the budget as a per-poll rate, and report per-flow flag rates.
- Report overflow tails (median, p90, share > 5 s) and per-domain tables.
- Reword §8.3 claim 3 as in item 3 above.

## 10. Revision step 1 — service-level harm, tails, cluster CIs, per-flow calibration

These changes respond to review items 2, 6, 7 and 8.

- Code: `loftbench/revision1.py`, plus the harm accounting in `loftbench/sim.py`.
- Tables: `results/revision1/tables/`.
- **No configuration was selected or changed.** The v2.1 test configuration was
  re-measured on the same seeds (5000–5009) with the extra metrics. All 1,680 episodes
  reproduce every original metric exactly (`determinism_check.json`).
- The per-flow-calibrated variant was evaluated on **validation seeds only**, so seeds
  6000+ remain unused.

### 10.1 New harm metric

A benign flow is **harmed** in either of two cases:

1. It was refused a table entry at least once, which puts it on the controller slow
   path.
2. Its entry was removed while the flow was still active, meaning its next packet
   arrived before the entry would have idled out.

Removing a stale entry is counted separately and is not harm. Extra Packet-In is
measured against the same benign traffic with no attack and no defense, paired on
(domain, seed). Unit tests: `test_active_vs_stale_eviction_harm` and
`test_rejection_counts_as_harm`.

**Confidence intervals and tests from here on resample whole (domain, seed)
clusters**: 30 clusters of 7 attacked episodes each, which share benign traffic.
Tests are cluster-level Wilcoxon with Holm correction (`cluster_paired_tests.csv`).

| Defense | Harmed (%) | Refused (%) | Evicted while active (%) | Stale removed (%) | Old "impacted" (%) | Extra Packet-In / 1k benign pkts | Malicious occ. (%) |
|---|---|---|---|---|---|---|---|
| No defense | 42.77 [41.63, 43.90] | 42.77 | 0.00 | 0.00 | 42.77 | 132.7 | 53.45 |
| DMS-BTT | 7.92 [6.57, 9.32] | 4.73 | 3.80 | 4.33 | 12.09 | 21.1 | 24.93 |
| Local MLP + v2 policy | 11.19 [8.57, 13.96] | 2.04 | 10.29 | 8.50 | 19.61 | 54.5 | 25.89 |
| Local MLP (no ctx) + v2.1 policy | 7.61 [6.59, 8.62] | 7.13 | 0.65 | 1.38 | 8.95 | 23.3 | 20.74 |
| FL-DualGuard v2 | 3.63 [2.60, 4.72] | 0.94 | 2.92 | 2.30 | 5.91 | 10.6 | 14.97 |
| **FL-DualGuard v2.1** | **1.73 [1.27, 2.18]** | 1.20 | 0.61 | 0.52 | 2.24 | **5.4** | **14.43** |
| Pooled oracle (v2 policy) | 2.81 [1.98, 3.70] | 0.75 | 2.21 | 2.51 | 5.30 | 10.9 | 13.93 |

**v2.1 compared with each baseline on harmed flows** (cluster level):

| Baseline | Cluster wins | p_Holm | Ratio |
|---|---|---|---|
| DMS-BTT | 30/30 | 1e-8 | 4.6× fewer harmed flows, down from 5.4× under the old metric |
| Local no-ctx, same policy | 30/30 | 1e-8 | 4.4× |
| v2 | 28/30 | 7e-8 | |
| Pooled (v2 policy) | 27/30 | 6e-5 | |

The ranking is unchanged. The gap to DMS-BTT narrows because more of DMS-BTT's
removals were stale entries.

### 10.2 Overflow tails (`table_overflow_tails.csv`)

| Defense | Mean [cluster CI] | Median | p90 | p99 | Max | > 5 s | > 10 s |
|---|---|---|---|---|---|---|---|
| DMS-BTT | 13.27 [8.93, 17.75] | 5.8 | 33.1 | 72.2 | 77.2 | 55.7 % | 35.7 % |
| Local no-ctx, same policy | 24.68 [21.97, 27.43] | 3.3 | 104.3 | 179.6 | 181.6 | 33.3 % | 26.7 % |
| FL-DualGuard v2 | 3.18 [2.48, 3.90] | 2.4 | 6.9 | 12.8 | 14.8 | 21.4 % | 3.8 % |
| **FL-DualGuard v2.1** | 4.89 [3.94, 5.85] | 3.9 | 8.8 | 26.2 | 27.7 | 41.4 % | 7.6 % |
| Pooled (v2 policy) | 2.47 [2.12, 2.83] | 2.2 | 4.7 | 10.3 | 13.4 | 7.1 % | 1.4 % |

**Corrections to earlier claims:**

1. **Overflow compared with DMS-BTT.** The improvement is **not significant at the
   cluster level**: −8.4 s mean, 20/30 cluster wins, p_Holm = 0.13. The earlier
   episode-level test (§8.2) overstated this. Report v2.1's tails as better (p90 8.8 s
   vs 33.1 s) but do not claim a significant mean difference.
2. **Overflow compared with v2 and pooled.** v2.1 is significantly worse (0/30 cluster
   wins). This is the price of dropping the hard guard.
3. **The 5 s overflow limit holds on the mean only.** Its CI is [3.94, 5.85], and
   41 % of episodes exceed it.
4. **Malicious occupancy compared with v2** is not significantly different
   (p_Holm = 0.26).

### 10.3 Per variant (v2.1, `table_v21_by_variant.csv`)

| | A1 | A2 | A3 | A4 | A5 | A6 | A7 |
|---|---|---|---|---|---|---|---|
| Harmed (%) | 1.66 | 1.46 | 1.66 | 3.17 | 1.58 | 1.10 | 1.44 |
| Malicious occ. (%) | 14.2 | 13.0 | 13.4 | **22.1** | 13.7 | 12.4 | 12.3 |
| Overflow mean / p90 (s) | 4.9 / 8.3 | 3.5 / 6.9 | 4.8 / 8.4 | **12.5 / 22.4** | 4.5 / 7.9 | 1.0 / 3.2 | 3.0 / 5.8 |

Against mimicry (A4), v2.1 exceeds both the occupancy limit and the overflow limit: it
keeps benign harm low but lets the attacker hold a larger share of the table. State
this in the main text.

### 10.4 Per domain (harmed %, cluster CIs, `table_harm_by_domain.csv`)

| Defense | D1 | D2 (IoT) | D3 (cloud) |
|---|---|---|---|
| DMS-BTT | 3.60 | 8.10 | 12.05 |
| Local no-ctx, same policy | 4.08 | 10.29 | 8.45 |
| **v2.1** | **0.47** | **3.09** | **1.61 [0.87, 2.45]** |

D2 is the hard domain: its periodic IoT telemetry flows resemble LFTO refreshes.

### 10.5 Per-flow calibration (review item 6; `table_flow_calibration.csv`)

The v2.1 threshold τ was calibrated per (entry, poll). Re-measuring it as a per-flow
quantity, meaning the fraction of benign flows that ever score ≥ τ while installed,
gives:

| Domain | τ per poll | τ per flow | Validation flows ≥ τ_poll | Test flows ≥ τ_poll (attacked / benign-only) | Test flows ≥ τ_flow (attacked / benign-only) |
|---|---|---|---|---|---|
| D1 | 0.0070 | 0.132 | 4.7 % | 2.6 % / 2.6 % | 0.7 % / 0.6 % |
| D2 | 0.0030 | 0.473 | 5.0 % | 6.3 % / 3.6 % | 1.5 % / 0.7 % |
| D3 | 0.0031 | 0.136 | 5.0 % | 4.0 % / 6.9 % | 0.6 % / 0.8 % |

**What this shows:**

- The declared "1 % budget" was in fact about 5 % per flow. Per-flow calibration holds
  1 % on validation, and 0.6–1.5 % on test runs. The D2 attacked case slightly exceeds
  the budget, because attack traffic shifts the score distribution.
- Under v2.1, the realized benign *action* rate on benign-only runs is 0–1.2 %. That
  is lower than the flag rate because the ρ = 0.7 occupancy gate keeps the policy idle.

**Validation-only comparison** (`table_flowcal_validation.csv`; 63 attacked plus 9
benign-only episodes):

| Variant | Harmed (%) | Benign flows acted on (%) | Malicious occ. (%) | Overflow mean / p90 (s) |
|---|---|---|---|---|
| v2.1 (τ per poll) | 1.45 [0.69, 2.32] | 1.11 | 14.47 | 4.55 / 9.4 |
| v2.1 (τ per flow) | 1.38 [0.70, 2.17] | 0.25 | 16.11 | 6.81 / 12.4 |

Per-flow calibration acts on 4× fewer benign flows at the same harm. However, it
breaks the pre-registered limits for malicious occupancy (≤ 15 %) and overflow (≤ 5 s).
Under the v2.1 rule it would not have been selected, so it is **not adopted here**.
Carry it as a candidate into the step-4 pre-registration, together with the
adaptive-attacker mechanism. The paper must state the budget correctly: either a
per-(entry, poll) rate of 1 % (about 5 % per flow), or per-flow calibration.

### 10.6 Wording changes required in the paper

- **No defense.** "42.8 % of benign flows impacted with no defense" becomes "42.8 % of
  benign flows were refused a table entry at least once". These flows were
  slow-pathed, not dropped.
- **Headline metric.** Use *harmed* (1.73 % for v2.1). Keep "impacted" only as a
  secondary column.
- **Ratios.** Use 4.6× fewer harmed flows than DMS-BTT and 4.4× fewer than local
  training under the identical policy. The earlier ratios were 5.4× and 4.0×.
- **Intervals and tests.** All CIs and tests become cluster-level.
- **Overflow.** Drop any claim of significantly lower mean overflow than DMS-BTT.
- **Still unmeasured.** Goodput and latency need the controller service model
  (plan P0-2 part 2) or the testbed.

## 11. Revision step 2 — a fair DMS-BTT comparison (review item 4)

Code: `loftbench/revision2.py`. Artifacts: `results/revision2/`.

**Protocol:**

1. **Pre-registration** (`0b7ede6`), committed before any selection episode: 96
   DMS-BTT candidates in five families, against v2.1's 24.
2. **Selection.** Each family was selected on validation seeds 2000–2002 using v2.1's
   rule (`7a1b1c1`). v2.1 never needed its fallback; the fallback here (least
   constraint violation, then the objective) applies only to DMS-BTT families that
   have no feasible candidate.
3. **One-shot test** on seeds 5000–5009. These seeds were never used to tune any
   DMS-BTT configuration. The v2.1, local, and no-defense rows are the deterministic
   re-measurement from §10, paired on identical traffic.
4. **Statistics:** cluster-bootstrap CIs and cluster-level Wilcoxon tests (Holm),
   with 30 (domain, seed) clusters.

**Families:**

| Family | What it is |
|---|---|
| A | DMS-BTT tuned: H2, H1, flow threshold, and Numb ∈ {bytes, packets} |
| B | A plus a blocklist: flows deleted as malicious are refused re-admission for T s, and their packets are dropped at the controller |
| C | DMS-BTT detector with the DualGuard policy (soft demotion), with an optional state gate |
| D | Federated DMS-BTT: a FedAvg MLP over (Numb, PIT, Sizep) with the two-level policy |
| E | Federated DMS features with the v2.1 policy |

**Validation selection** (`selection_table.csv`). Only family B has a configuration
that satisfies all of v2.1's limits.

| Family | Selected | Feasible | Val. impacted | Val. malicious occ. | Val. overflow |
|---|---|---|---|---|---|
| A | H2 = 0.6, H1 = 0.85, p = 0.7, bytes | no | 12.1 % | 21.8 % | 10.9 s |
| B | H2 = 0.6, H1 = 0.9, p = 0.7, bytes, T = 60 s | **yes** | 8.1 % | 13.9 % | 3.9 s |
| C | ρ = 0.7, no gate, hard guard 0.90, bytes | no | 8.7 % | 18.4 % | 2.6 s |
| D | H2 = 0.6, H1 = 0.9, p = 0.3 | no | 12.3 % | 21.9 % | 11.6 s |
| E | ρ = 0.7 | no | 10.4 % | 21.9 % | 31.3 s |

### 11.1 Test results (attacked episodes, n = 210 per defense)

| Defense | Harmed (%) | Malicious occ. (%) | Overflow mean / p90 (s) | > 5 s |
|---|---|---|---|---|
| No defense | 42.77 [41.63, 43.90] | 53.45 | 147.4 / 186.0 | 100 % |
| DMS-BTT, original knobs | 7.92 [6.57, 9.32] | 24.93 | 13.3 / 33.1 | 56 % |
| A: DMS-BTT tuned | 7.86 [6.38, 9.37] | 21.90 | 11.6 / 32.6 | 36 % |
| **B: DMS-BTT tuned + blocklist** | **4.71 [3.65, 5.73]** | **13.83 [12.60, 15.08]** | **4.1 / 6.7** | **12 %** |
| C: DMS-BTT detector + DualGuard policy | 4.13 [3.15, 5.17] | 18.25 | 2.8 / 5.5 | 11 % |
| D: DMS-BTT federated | 7.43 [5.93, 8.94] | 21.97 | 12.4 / 32.9 | 42 % |
| E: federated DMS features + v2.1 policy | 9.59 [8.94, 10.25] | 21.91 | 31.4 / 159.2 | 32 % |
| Local MLP (no ctx) + v2.1 policy | 7.61 [6.59, 8.62] | 20.74 | 24.7 / 104.3 | 33 % |
| **FL-DualGuard v2.1** | **1.73 [1.27, 2.18]** | 14.43 [13.90, 14.94] | 4.9 / 8.8 | 41 % |

**v2.1 against the strongest fair baseline (B).** Cluster-level Holm-corrected tests,
from `cluster_paired_tests.csv`:

| Metric | v2.1 vs B | Cluster wins | p_Holm | Verdict |
|---|---|---|---|---|
| Benign flows harmed | 1.73 % vs 4.71 % (2.7× fewer) | 30/30 | 1.5e-8 | v2.1 better |
| Malicious occupancy | 14.4 % vs 13.8 % | 11/30 | 0.12 | no difference |
| Mean overflow | 4.9 s vs 4.1 s | 10/30 | 1.0 | no difference |

B has better overflow tails: 12 % of episodes exceed 5 s, against 41 % for v2.1.

**Harmed % by variant** (`table_harmed_by_variant.csv`):

| Defense | A1 | A2 | A3 | A4 | A5 | A6 | A7 |
|---|---|---|---|---|---|---|---|
| DMS-BTT, original | 4.51 | 4.71 | 4.70 | 24.29 | 4.52 | 8.70 | 3.99 |
| B: tuned + blocklist | **0.46** | **0.41** | **0.30** | 21.74 | **0.44** | 9.25 | **0.33** |
| C: DMS detector + DG policy | 1.40 | 1.41 | 1.45 | 15.60 | 1.40 | 6.38 | 1.26 |
| E: fed DMS features + v2.1 policy | 1.24 | 1.22 | 1.25 | 50.36 | 1.23 | 10.77 | 1.08 |
| **v2.1** | 1.66 | 1.46 | 1.66 | **3.17** | 1.58 | **1.10** | 1.44 |

### 11.2 What this changes

1. **The DMS-BTT baseline in the paper must be the tuned-plus-blocklist variant (B).**
   - Against B, v2.1 harms **2.7×** fewer benign flows. The earlier figure, against the
     untuned DMS-BTT, was 4.6×.
   - v2.1 contains the attack **no better** than B: occupancy and mean overflow are not
     significantly different, and B's overflow tail is better.
   - Tuning DMS-BTT's thresholds alone barely helps (7.92 % → 7.86 %). The blocklist
     is what helps.
2. **On DMS-BTT's own attack settings, B beats v2.1 on benign harm.**
   - On A1–A3, A5 and A7, B harms 0.3–0.5 % of benign flows, against 1.4–1.7 % for
     v2.1.
   - v2.1's entire advantage comes from mimicry (A4: 3.2 % vs 21.7 %) and the
     variant unseen by any controller (A6: 1.1 % vs 9.3 %).
   - The paper's claim must therefore be **robustness to attack variants a controller
     has not seen, or that mimic benign traffic**, not general superiority.
3. **Decomposing the gain over DMS-BTT** (harmed %):

   | Step | Change | Harmed |
   |---|---|---|
   | DMS-BTT | — | 7.9 % |
   | C | Replace its policy with soft demotion | 4.1 % |
   | v2.1 | Our 17 features and federation | 1.7 % |

   Federating DMS-BTT's own 3 features barely helps (D: 7.4 %). With the v2.1 policy
   they fail badly on A4 (E: 50 %). Federation transfers cross-variant knowledge only
   with sufficiently rich features. This also previews step 3: the federation benefit
   is conditional, and it has to be shown against a shared-attack-library baseline.
4. **The Numb definition barely matters.** On validation (bytes vs packets), the best
   configuration's impacted % moves 12.1 → 13.2 (A), 8.1 → 8.8 (B), and
   8.7 → 9.5 (C). Feasibility is unchanged
   (`table_numb_sensitivity_validation.csv`). Whichever definition the paper uses, the
   conclusions hold. Report the paper's definition as primary once it is checked.
5. **Implication for step 4 (adaptive attacker).**
   - The blocklist's refuse-re-admission mechanism directly addresses the
     fast-refresh attacker: demotion only removes flows that refresh more slowly than
     t_short.
   - Combining DualGuard's calibrated scoring with a blocklist for repeatedly demoted
     flows is the obvious step-4 candidate.
   - It must be pre-registered and tested on seeds 6000+.
   - Note the blocklist's cost: it drops benign flows outright (0.30 % of benign flows
     were blocked in B), whereas demotion only slow-paths them.

## 12. Revision step 3 — is federation necessary? (review item 5)

Pre-registered in `results/revision3/preregistration.json` (commit `491d95f`, sha256
in `preregistration.sha256`) before any model was trained. Code:
`loftbench/revision3.py`. Tables: `results/revision3/tables/`.

**Design.** Every method uses the same 17 features, the same MLP, the same v2.1 policy
(ρ = 0.7, t_short = 1 s, no hard guard) and the same calibration (1 % budget on its own
domain's validation benign). Only the training data each controller can use differs:

| Method | Training data per controller |
|---|---|
| Local only | Own domain (2 of 7 variants) |
| FedAvg (v2.1) | Own domain; weights averaged across the 3 controllers |
| Pooled raw data (oracle) | All three domains' raw records |
| Ensemble of local models | Own domain; at test time, mean score of the 3 local models |
| Local + public library (A1–A3) | Own domain + the three published DMS-BTT settings |
| Local + library of all known variants | Own domain + every variant except A6 (upper bound) |

Fresh evaluation seeds 7000–7009 (never used before); 30 (domain, seed) clusters;
cluster Wilcoxon with Holm correction. Seeds 6000+ remain untouched for step 4.

**Post-registration bug fixes (implementation only, design unchanged).** The first
run crashed in the exposure-skew sweep. (1) The attack-row budget `n_att` was summed
with Python's built-in `sum` over an int8 label array, which overflowed and went
negative. (2) Each variant's sample was capped at the rows available, so the
pre-registered fixed total was not honoured. Both are fixed in `_sweep_task`; the
main and leave-one-variant-out code paths were not affected. All stages were rerun
from training.

### 12.1 Pre-registered decision

| Comparison (benign flows harmed) | FedAvg − comparator | FedAvg wins / losses (30 clusters) | Holm p |
|---|---|---|---|
| Local + public library (A1–A3) | **−4.21 points** | 28 / 2 | 5 × 10⁻⁸ |

**Federation is necessary relative to a public attack library** (rule: Holm p < 0.05
and difference ≥ 0.5 points). The paper keeps cross-controller learning as a core
claim. The re-scope to a mitigation-only paper is **not** triggered.

### 12.2 Main comparison (attacked episodes, seeds 7000–7009)

| Method | Harmed % [95 % cluster CI] | Malicious occupancy % | Overflow mean / p90 (s) | Share > 5 s |
|---|---|---|---|---|
| No defense | 42.21 [41.08, 43.39] | 53.29 | 147.4 / 188.3 | 1.00 |
| DMS-BTT tuned + blocklist | 4.49 [3.45, 5.52] | 13.79 | 3.77 / 5.47 | 0.11 |
| Local only | 7.89 [7.25, 8.57] | 23.10 | 29.2 / 119.6 | 0.61 |
| **FedAvg (v2.1)** | **1.53 [1.12, 1.98]** | 14.49 | 4.71 / 9.31 | 0.36 |
| Pooled raw data (oracle) | 1.69 [1.14, 2.27] | 13.70 | 3.10 / 5.72 | 0.12 |
| Ensemble of local models | 1.42 [1.06, 1.82] | 15.12 | 5.64 / 11.23 | 0.41 |
| Local + public library (A1–A3) | 5.75 [4.33, 7.15] | 19.87 | 19.8 / 44.5 | 0.42 |
| Local + all known variants | 1.49 [1.17, 1.83] | 15.51 | 5.26 / 12.22 | 0.31 |

Paired against FedAvg (`cluster_paired_tests_main.csv`):

- **vs public library:** FedAvg better on harm (−4.2 points), occupancy (−5.4 points)
  and overflow (−15.1 s); all 28–30 / 30, Holm p < 10⁻⁷. The library fails exactly
  where it has no coverage: A4 mimicry (29.7 % harmed) and A6 slow-fill (5.3 %).
- **vs pooled oracle:** harm not different (12 / 18, p = 0.88): H4 holds. Pooled has
  lower occupancy (0.8 points) and overflow (1.6 s), 30 / 30.
- **vs ensemble of local models:** harm not different (−0.11 points in the
  ensemble's favour, 10 / 20, Holm p = 0.074). FedAvg is better on occupancy
  (−0.6 points, 30 / 30) and overflow (−0.9 s, 28 / 2). **H2 is not supported.**
- **vs library of all known variants:** no difference on any metric (H3 not
  supported). This upper bound assumes a generator for every variant is public.
- **vs DMS-BTT tuned + blocklist:** 2.9× fewer harmed (28 / 2, Holm p = 2 × 10⁻⁷);
  occupancy and overflow not significantly different. This reproduces §11 on fresh
  seeds.

### 12.3 Leave-one-variant-out (each variant withheld from every controller)

Online, benign harmed % on the withheld variant (5 seeds × 3 domains per variant):

| Held out | Local | FedAvg | Pooled | Ensemble | Library A1–A3 | Library all |
|---|---|---|---|---|---|---|
| A1 | 2.46 | 7.37 | 1.25 | 1.57 | 6.56 | 1.61 |
| A2 | 18.32 | 1.67 | 0.78 | 1.07 | 18.15 | 0.98 |
| A3 | 9.68 | 1.65 | 1.31 | 1.68 | 1.38 | 1.62 |
| A4 | 26.07 | 3.33 | 5.37 | 12.23 | 24.68 | 3.68 |
| A5 | 2.23 | 1.63 | 4.17 | 1.47 | 2.79 | 1.55 |
| A6 | 4.67 | 0.90 | 1.21 | 0.63 | 5.66 | 0.45 |
| A7 | 11.56 | 1.96 | 1.96 | 2.10 | 0.73 | 1.12 |
| **Mean [CI]** | 10.71 [9.31, 12.15] | **2.64 [1.59, 3.84]** | 2.29 [1.44, 3.25] | 2.97 [2.42, 3.62] | 8.56 [6.35, 10.90] | 1.57 [1.00, 2.22] |

(Library columns exclude the withheld variant from the library as well.)

Paired tests over 105 (variant, domain, seed) pairs (`lovo_online_tests.csv`):
FedAvg beats local by 8.1 points (69 / 36, Holm p = 10⁻⁶). Against the public library
the mean gap is 5.9 points but the pairs split 50 / 55 (Holm p = 0.099): FedAvg wins
by large margins on A2, A4 and A6 and loses on A1 and A7. **H5 holds against local
training, not against the library.**

The A1 row is a real weakness: with A1 withheld, FedAvg harms 7.4 % against 2.5 % for
local. The averaged model generalises worse to that variant than a local model does.
It should be reported.

Offline, held-out TPR (`table_lovo_offline_tpr.csv`): FedAvg is ≥ 0.83 on every
withheld variant except A6 (0.69); local ranges 0.21–0.72. The hardest variant is A4
mimicry, where FedAvg (0.83) beats even the pooled oracle (0.31).

### 12.4 Exposure-skew sweep (offline, `table_skew_sweep_offline.csv`)

Each controller's attack rows are a Dirichlet(α) mix of the six known variants with a
fixed total; 3 draws per α.

| α | Skew | FedAvg − local TPR (mean ± sd) | TPR on rarely seen variants (w < 5 %): local / FedAvg / ensemble |
|---|---|---|---|
| 0.05 | extreme | **+0.137 ± 0.287** | 0.672 / 0.850 / 0.847 |
| 0.2 | high | +0.042 ± 0.161 | 0.896 / 0.962 / 0.951 |
| 1.0 | moderate | +0.016 ± 0.091 | 0.883 / 0.930 / 0.932 |
| 5.0 | low | +0.000 ± 0.017 | 0.881 / 0.890 / 0.895 |
| ∞ | uniform | +0.001 ± 0.017 | 0.834 / 0.848 / 0.876 |

**H6 holds:** the federation gain grows monotonically with skew and vanishes when
every controller sees every variant. FPR stays at 0.8–1.2 % throughout.

### 12.5 Hypotheses

| | Hypothesis | Outcome |
|---|---|---|
| H1 | FedAvg harms fewer than the public library (main) | **Supported** (−4.2 points, Holm p = 5 × 10⁻⁸) |
| H2 | FedAvg harms fewer than the ensemble of local models | **Not supported** (no difference; FedAvg better on occupancy/overflow) |
| H3 | FedAvg harms fewer than the library of all known variants | **Not supported** (no difference) |
| H4 | FedAvg within 1 point of pooled | **Supported** (−0.15 points, n.s.) |
| H5 | On withheld variants, FedAvg beats local and the public library | **Partly**: vs local yes; vs library n.s. (50 / 55) |
| H6 | The gain shrinks as exposure skew decreases | **Supported** |

### 12.6 What the paper should claim

1. **Keep cross-controller learning as a core contribution.** A controller that sees
   only some variants, even with the published DMS-BTT attack settings added, harms
   3.8× more benign flows than FedAvg and overflows 4× longer.
2. **Claim sharing of learned knowledge, not FedAvg specifically.** A one-shot
   ensemble of the three local models matches FedAvg on harm. FedAvg's advantages
   over it are smaller: lower occupancy and overflow, and one model to run per poll
   instead of three. Write the method as "cross-controller model sharing, instantiated
   with FedAvg", with the ensemble as an ablation row.
3. **State the regime.** The gain exists only when controllers see different attack
   variants (α ≤ 1). Under uniform exposure, local training is enough. Frame
   federation as the answer to heterogeneous exposure, not as a universal improvement.
4. **Do not claim generalisation to unseen variants in general.** Against local
   training it holds; against a public library it is not significant, and A1 is a
   counter-example.
5. **Equivalence with the pooled oracle is now like-for-like** (same v2.1 policy):
   FedAvg matches pooled on harm, with slightly worse occupancy and overflow.

## 13. DMS-BTT fidelity check against the paper (review item 4)

Source: Tang et al., "DMS-BTT", Expert Systems with Applications 293 (2025) 128685,
§4.1–4.2, Table 1, Algorithms 1–2 and §5 (PDF supplied by the authors of this work).

**Numb is the cumulative byte count** (Table 1: "Cumulative number of bytes";
§4.2.1). Our primary configuration (`numb_mode="bytes"`, `features.py`) is therefore
the paper's definition, and every DMS-BTT number in §3, §8, §11 and §12 stands. The
packet-count variant from step 2 is only a sensitivity check (it moved validation
harm by under 1 point).

| Detail | Paper | Ours | Status |
|---|---|---|---|
| Numb | Cumulative bytes | Bytes | Matches |
| PIT | Duration / packets; duration if no packets (Alg. 1, l. 9–13) | Duration / max(packets, 1) | Matches |
| Sizep | Bytes / packets; 0 if no packets | Bytes / max(packets, 1) | Matches |
| State features | FN and APIT = mean PIT; three classes | Same | Matches |
| Thresholds | H2 = 75 %, H1 = 90 % of the table | 0.75 / 0.90 | Matches |
| Table, idle timeout, polling | 3,500, 10 s, 1 s | Same | Matches |
| Attack settings | Table 2: T1 ∈ [5, 8.5], [5.5, 9], [6, 9.5]; S = 75, 100, 125; M = 1,700 | A1–A3 | Matches |
| Between H2 and H1 | State classifier; if attack, evict flows labelled malicious | Same | Matches |
| Above H1 | No state check; evict top Pe × FN by probability (Pe ∈ 15–30 %, value for Table 6 not stated) | State check required; evict labelled + descending probability until below H2 | **Deviation** |
| Elephant protection | Keep if Numb, PIT and Sizep all exceed their 90th percentile (Alg. 2; text says "or") | Keep if Numb ≥ 90th percentile | **Deviation** |
| CatBoost settings | Not reported | 300 iterations, default depth; flow threshold tuned in step 2 | Unspecified |

**Assessment.**

- The two deviations are both in the overflow-prevention branch above 90 %
  occupancy. Our gating can only make DMS-BTT act *less* often above H1. Our
  eviction amount (to below 75 %, about 15–17 % of entries) is comparable to the
  paper's smallest Pe.
- The step-2 baseline (tuned + blocklist) already searched thresholds on validation,
  so DMS-BTT was not handicapped by an untuned operating point.
- To close the question for reviewers, add a paper-faithful mode (no gating above H1,
  Pe ∈ {15, 20, 25, 30} %, three-feature elephant rule), select Pe on validation seeds
  only, and test it once on fresh seeds alongside v2.1. Until then, describe our
  baseline as "a reimplementation following Algorithms 1–2, with the two deviations
  listed".
