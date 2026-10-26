# Paper draft — FL-DualGuard: Federated, Budget-Calibrated Soft Mitigation of Low-Rate Flow-Table Overflow Attacks Across SDN Controllers

> Draft of 26 October 2026. The headline numbers come from the v2.1 configuration,
> re-measured with the service-level harm metric and cluster-bootstrap CIs
> (`results/revision1`, `docs/results_v2.md` §10; earlier §8). The v2 results
> (`results/v2`) serve as the first design and the ablation study.
> Text marked **[TODO]** needs the emulation run, citations, or author decisions before
> submission. Keep the negative findings: reviewers will reproduce the benchmark.

## Abstract

Low-rate flow-table overflow (LFTO) attacks exhaust the bounded flow tables of SDN
switches by keeping many malicious entries alive with a few packets each, just below
the idle timeout. Existing defenses train a detector on one controller's own
observations, then delete or block flows. They fail when an attacker uses a variant
the controller has not seen, and the deletions themselves disrupt legitimate traffic.

We present FL-DualGuard, a defense for multi-controller SDN with three parts:

1. A shared flow detector, trained by federated learning across administrative domains
   without exchanging flow records.
2. Per-controller calibration of the action threshold to a declared benign-disruption
   budget.
3. A *soft demotion* action: a suspected entry is removed and reinstalled with a 1 s
   idle timeout. A misclassified benign flow keeps being forwarded, while an LFTO flow
   loses most of its table residency.

The final configuration was selected on validation runs under a pre-registered rule
and tested once on fresh runs.

We also release LOFT-Bench, a test-covered multi-controller LFTO benchmark. It has
three heterogeneous domains, seven attack variants (including the DMS-BTT parameter
sets, mimicry, spoofing, slow-fill and pulsing), run-disjoint splits, and paired
online evaluation.

Across 210 attack episodes per defense (30 independent traffic clusters),
FL-DualGuard harms 1.7 % of benign flows. Here, harm means the flow was refused a
table entry, or was evicted while still active.

The strongest baseline is DMS-BTT given the same tuning budget plus a blocklist. It
harms 4.7 %, which is 2.7× more, and contains the attack equally well (14 % malicious
occupancy for both). On DMS-BTT's own attack settings, the tuned blocklist variant is
better (about 0.4 % vs 1.6 %). FL-DualGuard's advantage comes from attack variants
that a controller has not seen, or that mimic benign traffic: 1.1–3.2 % against
9–22 %.

An ablation attributes the gain to the soft-demotion policy (7.9 → 4.1 %) and to
federated training over richer flow features (4.1 → 1.7 %). Federating DMS-BTT's
three features alone does not help. **[TODO: rewrite after steps 3–4: the shared
attack-library comparator, and the adaptive attacker that refreshes faster than 1 s.]**

We also report where the first design fell short. Its pre-declared FedProx optimizer
and hard overflow guard both hurt benign traffic, and removing the guard costs about
1.7 s more overflow per 300 s.

**[TODO]** Add one sentence on the Mininet/OVS confirmation.

## 1. Introduction

1. **The LFTO problem.** Bounded TCAM and flow tables, reactive rule installation, and
   low-rate refresh just under the idle timeout. Legitimate new flows are refused
   (`OFPFMFC_TABLE_FULL`) and pushed to the slow path.
2. **Why existing defenses fall short.** FTMaster, FTOP, FloRa, FTSheild and DMS-BTT
   all detect with features local to one controller, then delete or blacklist
   **[cite]**.
   - Two problems follow. (i) A controller only knows the variants it has observed. In
     our benchmark, a local detector's AUC drops from 1.00 to 0.88 on variants seen
     elsewhere, and to 0.68 on a never-seen variant. (ii) Hard deletion converts every
     false positive into service disruption. DMS-BTT impacts *more* benign flows than
     no defense on a slow-fill variant (17.9 % vs 12.2 %).
3. **Insight.** Controllers in different domains observe different attack variants.
   Collaboration can share that knowledge without sharing traffic. The mitigation
   action should also be cheap to get wrong.
4. **Contributions.**
   - **C1, FL-DualGuard.** Federated detector, budget-calibrated thresholds, and soft
     demotion with an optional hard guard.
   - **C2, LOFT-Bench.** An open, test-covered simulator and benchmark protocol with
     heterogeneous exposure and run-disjoint splits, plus a Mininet/OVS/Ryu harness that
     shares the same feature extractor.
   - **C3, evaluation.** A paired evaluation against six baselines and an oracle, with
     ablations. It includes negative results that bound which parts of the design
     matter.

## 2. Background and threat model

- **OpenFlow 1.3 tables:** idle timeouts are integer seconds; table-full errors;
  flow-stats polling.
- **Attacker** (methodology §2, Table 1): the DMS-BTT recurrence
  N_i = N_{i-1} + S, refreshed every t1 < idle timeout, with M = 1700 flows per
  attacker. Stronger variants are A4–A7.
- **Defender:** sees only OpenFlow state. All user traffic enters through one uplink,
  so the ingress port does not identify attackers.
- **Federation:** an honest-but-curious aggregator receives weights and normalization
  sufficient statistics only. Poisoning is out of scope (§8).

## 3. Design

### 3.1 Features

There are 17 causal features from flow-stats deltas and the controller's own poll
history (methodology §4). The same extractor runs for all flows and is reused verbatim
by the Ryu application.

### 3.2 Federated detector

- **Model:** a 17→32→1 MLP (609 parameters).
- **Normalization:** federated, from per-client (n, Σx, Σx²).
- **Training:** 30 rounds of FedAvg, one local epoch per round. FedProx (μ = 0.01)
  was the v2 choice; validation selection preferred FedAvg.
- Each client applies the received global weights before local training and before
  inference.

### 3.3 Budget calibration

Each controller sets τ_k as the (1 − β) quantile of benign scores from its *own*
validation runs, with β = 1 %. On held-out runs the realized benign flag rate is
1.0–1.1 %. This is an empirical guarantee, not a distribution-free one.

### 3.4 Dual action

At each one-second poll, when occupancy ≥ ρ (ρ = 0.7, selected on validation runs):

- **Soft demotion.** Entries with score ≥ τ_k are demoted: deleted now and reinstalled
  on their next Packet-In with idle timeout t_short = 1 s.
  - *Why this works:* an LFTO flow refreshed every 5–10 s then occupies an entry for
    about 1 s per period instead of the whole period. To hold its occupancy, the
    attacker must raise its packet rate by a factor of t1 / t_short, which removes the
    "low-rate" property.
  - *Cost of a mistake:* a benign false positive pays one extra Packet-In and keeps
    being forwarded.
- **Optional hard guard.** If occupancy is still ≥ h_crit after demotion, delete the
  highest-scoring non-elephant entries until occupancy reaches 0.8.
  - v2 enabled it with h_crit = 0.9.
  - v2.1 disables it: validation selection found that it trades benign evictions for
    overflow time (§7).

**[TODO]** Position soft demotion against adaptive and dynamic idle-timeout schemes
**[cite]**. The novelty claim is the combination with federated, calibrated scoring,
not adaptive timeouts per se.

## 4. LOFT-Bench

Summarize methodology §3 and §5:

- **Simulator semantics**, plus the unit tests that pin them: admission up to capacity,
  idle expiry versus refresh, Packet-Out to the table, OVS eviction, and demotion.
- **Domains:** enterprise, IoT (periodic hard negatives), and cloud (flash crowds).
- **Variants:** seven, with heterogeneous training exposure; A6 is never trained on.
- **Splits:** seed ranges disjoint across train, validation, offline test and online
  test.
- **Labels:** from provenance and observed table-full events. They are never derived
  from features (this fixes the circular labeling in the earlier prototype).

## 5. Evaluation setup

- **Methods** (methodology §6). DMS-BTT is reimplemented with CatBoost state and flow
  classifiers, two-level thresholds 0.75 / 0.90, and elephant protection.
  **[TODO]** Verify against the original Section 4.
- **Metrics:** benign flows impacted (primary), malicious occupancy, overflow time,
  Packet-In, and decision time.
- **Statistics:** 95 % bootstrap CIs; paired Wilcoxon tests with Holm correction.
- **Hardware:** 4-core Ubuntu 24.04 machine. Decision times are single-threaded
  wall-clock measurements.

## 6. Results

Use the tables and figures in `docs/results_v2.md`: §8 for the v2.1 headline, §2–§5
for the offline analysis and v2 ablations. Figures are in `results/v2/figures/`, plus
`results/v21/figures/fig7_v21_per_variant`.

| Item | Content |
|---|---|
| Table 2 (headline) | v2.1 one-shot test (results §8.1) |
| Fig. 7 | v2.1 per-variant benign impact |
| Table 3 | Selection protocol: pre-registration, validation table, then test |

The v2 tables and figures below support the design analysis and ablations:

| Figure | Content |
|---|---|
| Fig. 1 | Occupancy timelines: D1/A2, D2/A6 (unseen), D3/A4 (mimicry) |
| Fig. 2 | Main comparison: benign impact and malicious occupancy |
| Fig. 3 | Offline AUC by exposure group |
| Fig. 4 | FL convergence |
| Fig. 5 | Ablation |
| Fig. 6 | Per-variant benign impact |
| Table 3 | Main table with confidence intervals |
| Table 4 | Exposure breakdown: local 25.1 % → federated 6.5 % on variants seen only by others |

Key messages, in order:

1. Headline (v2.1, fresh seeds): 2.24 % benign impact, compared with 12.09 % for
   DMS-BTT and 8.95 % for local training under the identical policy. Malicious
   occupancy is 14.4 %; overflow is 4.9 s per 300 s.
2. Federation matters most for variants a controller has not seen. In v2 the gap is
   25.1 % → 6.5 % for variants seen only by other controllers. In v2.1, the never-seen
   A6 variant gives 1.9 % against DMS-BTT's 18.1 %.
3. Soft demotion is the most important component. Without it, malicious occupancy
   rises from 15.0 % to 28.5 % and overflow time from 3.0 s to 9.6 s.
4. The advantage over DMS-BTT is largest on mimicry (3.9 % vs 42.2 %) and unseen
   variants. On DMS-BTT's own fixed-size settings, v2.1 still halves benign impact
   (about 2 % vs about 5 %).
5. Costs (v2.1): 23.7 % more Packet-In, 0.45 % of benign flows demoted when there is
   no attack, 439 KB of federated communication, and a 7.5 ms p99 decision loop.

## 7. Discussion: negative findings

State them as in results §5:

- FedProx ≈ FedAvg.
- Context-feature shift. In v2's test ablation, removing the context features helped.
  Validation selection still kept them under FedAvg without the hard guard, so the
  shift interacts with the hard guard.
- The hard guard's trade-off. This motivated v2.1, through a pre-registered
  validation-only selection rather than test-set tuning.
- SVM-RF: competitive on benign impact but 33× slower.

Each points to a concrete design guideline: train on defended trajectories, or omit
occupancy features; make the hard guard opt-in.

## 8. Limitations and ethics

- The primary results come from simulation. **[TODO]** Add the emulation confirmation.
- Benign traffic is parametric (bigFlows-like) rather than replayed traces.
- There are only three clients, which are honest; there is no secure aggregation or
  differential privacy.
- An adaptive attacker that knows t_short could raise its refresh rate. This trade-off
  should be quantified: occupancy versus attacker packet budget.
- Mimicry (A4) is still hard for every method.
- All experiments ran in isolated emulation and simulation; the attack code is for
  lab use only.

## 9. Related work [TODO — expand with citations]

- LOFT/LFTO detection and mitigation: FTMaster, FTOP, FloRa, FTSheild, DMS-BTT.
- Federated SDN intrusion detection: FedSec; Ali et al. 2023; FL-NDR 2026.
- Flow-table management with adaptive timeouts.
- Federated learning under heterogeneity: FedAvg, FedProx.

## 10. Artifact

LOFT-Bench, all scripts, the seeds, and the exact commands are in the repository. The
full pipeline takes about 1.5 h on 4 cores.
