# FL-DualGuard v2 — methodology and experiment contract

Status date: 25 October 2026. This document supersedes the readiness statements in
`methodology_loft_vs_dms_btt.md` and closes the blockers listed in `HANDOFF.md` §7
for the simulation track. Code: `loft_project/loftbench/`, tests: `loft_project/tests/`.

## 1. Problem and claim

Low-rate flow-table overflow (LFTO) attacks keep many entries alive in an SDN switch's
bounded flow table by refreshing each malicious flow just before its idle timeout.
Legitimate new flows are then refused (`OFPFMFC_TABLE_FULL`) and fall back to the
controller slow path.

**Research question.** Can SDN controllers in different administrative domains,
each exposed to *different* LFTO variants, collaborate without sharing flow records
so that every domain defends against variants it has never seen, at a declared
budget of benign disruption and small controller cost?

**Contribution (to be confirmed by results, §8).**
1. *FL-DualGuard*: a per-controller policy that combines (a) a detector trained by
   genuine federated learning (FedProx over a shared MLP; weights applied by every
   client), (b) per-controller calibration of the action threshold to a declared
   benign flag-rate budget (Neyman–Pearson style, local validation runs only), and
   (c) dual action under table pressure: *soft demotion* (delete; reinstall on the
   next Packet-In with a 1 s idle timeout) for flagged entries plus a *hard
   overflow guard* that evicts the highest-scoring non-elephant entries only if
   occupancy still exceeds 90 %.
2. *LOFT-Bench*: an open, test-covered multi-controller LFTO benchmark with
   heterogeneous domains, seven attack variants (three DMS-BTT parameter sets and
   four stronger adversaries), run-disjoint splits, and paired online evaluation.

Soft demotion is the key mechanism: a benign false positive pays one additional
Packet-In and stays forwardable, whereas an LFTO flow refreshing every 5–10 s keeps
its entry for only ~1 s per period, which defeats the "low-rate" premise. Adaptive
timeouts and ML eviction individually have prior art (see §9); the claim is the
combination with cross-domain federated knowledge under a calibrated budget.

## 2. Threat model

- Attackers are hosts inside a domain (two per domain, DMS-BTT), sending UDP packets
  that each create a distinct 5-tuple entry at the monitored switch.
- They follow the DMS-BTT recurrence N_i = N_{i-1} + S: each burst refreshes every
  live attack flow and opens S new flows until M = 1700 flows per attacker. The gap
  between bursts is t1 ~ U(t1_range), with t1 below the idle timeout.
- Stronger variants may spoof sources, mimic benign packet sizes and counts, fill
  slowly near the timeout, or pulse on/off (Table 1).
- The defender sees only OpenFlow 1.3 state: flow-stats (packet/byte counts,
  duration, match), Packet-In, and errors. All user traffic enters the monitored
  switch through one uplink, so the ingress port does not identify attackers.

| Variant | S | t1 (s) | pkts/refresh | sizes | sources | notes |
|---|---|---|---|---|---|---|
| A1 | 75 | 5.0–8.5 | 1 | 64 B | /24 pool | DMS-BTT set 1 |
| A2 | 100 | 5.5–9.0 | 1 | 64 B | attacker IP | DMS-BTT set 2 |
| A3 | 125 | 6.0–9.5 | 1 | 64 B | /24 pool | DMS-BTT set 3 |
| A4 | 100 | 6.0–9.5 | 1–3 | benign-like | /24 pool | mimicry |
| A5 | 100 | 5.5–9.0 | 1 | 64 B | spoofed per flow | spoofing |
| A6 | 45 | 8.0–9.8 | 1–2 | benign-like | spoofed per flow | slow fill; **never in training** |
| A7 | 300 | 5.0–8.0 | 1 | 64 B | attacker IP | 60 s on / 30 s off pulses |

## 3. Environment

**Simulation track (primary, executed).** `loftbench/sim.py` is a discrete-time
(0.1 s) model of a switch and its controller:

- Bounded table: 3,500 entries including the table-miss rule. Idle timeout 10 s.
  Rules are installed reactively per 5-tuple.
- Table misses produce Packet-In. Admission fails when the table is full; every
  packet of a rejected flow is a Packet-In plus a TABLE_FULL error and takes the
  slow path.
- Flow-stats polling every 1 s. Defenses act at each poll; deletion is immediate.
- OVS `overflow_policy=evict` is modeled as switch-side eviction of the
  soonest-to-expire entry.

It does **not** model link queueing, controller CPU saturation, or TCAM/ASIC timing.
Service impact is therefore reported as flow admission failure, eviction, and
Packet-In load, not as latency.

**Domains.** Each domain has its own controller and differs in benign traffic:

- **D1-enterprise**: bigFlows-like mixture, ~85 new flows/s.
- **D2-IoT**: 35 % long-lived periodic telemetry flows with 2–9.8 s periods, which are
  the natural hard negatives.
- **D3-cloud**: more elephants plus two benign flash crowds per 300 s, each about
  120 new flows/s from many external sources.

All domains use Zipf-distributed client popularity. Benign traffic for a given
(domain, seed) is identical under every variant and defense, so comparisons are
paired.

**Emulation track (harness written, needs sudo).** `loft_project/testbed/` builds the
DMS-BTT topology per domain in Mininet:

- One controller, two switches, and six user hosts (two of them attackers), plus a
  server. The inter-switch link is 250 Mb/s / 15 ms; host links are 1 Gb/s / 2 ms.
- An OVS `Flow_Table flow_limit=3500 overflow_policy=refuse` keeps no-defense
  overflow observable rather than masked by eviction.
- A Ryu app reuses `loftbench.features` and the exported FL-DualGuard model.
- Traffic drivers replay the simulator's exact schedules as real packets and log
  ground-truth 5-tuples.

See `testbed/README.md`.

## 4. Features (one causal extractor, `loftbench/features.py`)

All flows pass through the same extractor at every poll. Features never depend on
labels. They use only the flow-stats reply and the controller's own poll history and
install log. There are 17 features in three groups:

- **Per-entry (11):** log packets, log bytes, log duration, mean size, log rate, log
  PIT, log Δpackets since the last poll, idle polls, active-poll ratio, CV and mean of
  activity gaps.
- **Per-source (3):** entries from the same source, entries from that source installed
  in the last 10 s, and the small-flow fraction for that source. Spoofing defeats
  this group, and ablation measures its contribution.
- **Table context (3):** occupancy, install rate, and table APIT.

DMS-BTT inputs (FN, APIT, Numb, PIT, Sizep) come from the same snapshots.

## 5. Labels and splits

- **Entry labels** come from traffic provenance: whether the attack driver or the
  benign generator created the flow.
- **DMS-BTT state labels** come from attack timing and *observed* table-full events:
  - 0: no attack is active.
  - 1: an attack is active, but overflow has not yet occurred in this attack phase.
  - 2: an attack is active, and overflow has occurred.
- Runs are independent episodes with a recorded `run_id`. The seed ranges below are
  disjoint, which a unit test enforces:

  | Split | Seeds | Variants per domain | Duration | Use |
  |---|---|---|---|---|
  | Train | 1000–1004 | Own exposure set, plus benign-only runs | 240 s | Fitting |
  | Validation | 2000–2002 | Own exposure set, plus benign-only runs | 240 s | Calibration and policy tuning |
  | Offline test | 3000–3004 | All seven, plus benign | 240 s | Detector metrics |
  | Online test | 4000–4009 | All seven, plus benign | 300 s, onset at 50 s | Defense comparison |

- **Heterogeneous exposure in training:** D1 sees {A1, A4}, D2 sees {A2, A5}, and D3
  sees {A3, A7}. No domain ever trains on A6.
- Every test domain therefore faces three kinds of variants: *seen locally*, *seen
  only by other controllers*, and *unseen by all* (A6).

## 6. Methods compared

| Name | Detector | Training | Action |
|---|---|---|---|
| No defense | — | — | — |
| OVS evict | — | — | switch evicts soonest-expiring entry when full |
| Threshold-LRU | — | — | ≥90 % occupancy → delete lowest-rate entries to 75 % |
| DMS-BTT (reimpl.) | CatBoost state (FN, APIT) + CatBoost flow (Numb, PIT, Sizep) | local | two-level thresholds 0.75/0.90, elephant protection |
| Local SVM-RF + DG | soft-voting SVM+RF (legacy FL-DualGuard) | local | DualGuard policy |
| Local MLP + DG | MLP | local | DualGuard policy |
| FedAvg + DG | MLP | FedAvg, 30 rounds | DualGuard policy |
| **FL-DualGuard** | MLP | **FedProx (μ=0.01), 30 rounds** | DualGuard policy |
| Centralized pooled | MLP | pooled raw data (privacy-violating upper bound) | DualGuard policy |

All DualGuard variants share the same knobs (tuned on validation, `tune.py`) and the
same per-domain calibration budget (1 % benign flag rate), so detector differences
are isolated from policy differences. The ablations remove soft demotion, the hard
guard, calibration (τ = 0.5), source features, or context features.

**DMS-BTT fidelity (checked against Tang et al., ESWA 293 (2025) 128685, §4 and
Algorithms 1–2; details in `results_v2.md` §13).** Matching the paper: Numb is the
cumulative **byte** count (Table 1, §4.2.1); PIT = duration / packets (duration when no
packets); Sizep = bytes / packets; APIT = mean PIT over the table; state classifier on
(FN, APIT) with three classes; thresholds H2 = 75 % and H1 = 90 % of a 3,500-entry
table; 10 s idle timeout; 1 s polling; elephant protection at the 90th percentile.

Deviations that remain:

- **Gating above H1.** The paper skips state detection above H1 and always runs
  overflow prevention; ours requires the state classifier to report an attack.
- **Eviction amount above H1.** The paper evicts the top Pe × FN entries by
  malicious probability, with Pe a fixed setting (15–30 % studied; the value used for
  Table 6 is not stated). Ours evicts entries labelled malicious, then continues in
  descending probability until occupancy falls below H2, which removes about 15–17 %
  of entries from 90 % occupancy (comparable to Pe = 15 %).
- **Elephant rule.** The paper protects a flow when its Numb, PIT and Sizep all
  exceed their 90th percentiles (Algorithm 2, line 11; the text says "or"). Ours
  protects on Numb alone.
- **CatBoost settings** are not reported in the paper; we use 300 iterations, default
  depth and a 0.5 threshold (tuned in revision step 2).

## 7. Metrics and statistics

**Online metrics** (per 300 s episode):

- Benign flows impacted: refused admission at least once, or evicted/demoted (primary).
- Benign flows rejected.
- Benign flows evicted or demoted.
- Average malicious occupancy after onset.
- Overflow time.
- Packet-In count.
- Controller decision-loop time (feature extraction, inference, and actions; measured
  wall clock).

**Offline metrics:**

- Per-entry ROC AUC, TPR at 1 % FPR, and precision/recall/F1/FPR at the calibrated
  threshold.
- DMS-BTT three-state accuracy and attack detection rate (ADR).
- Federated communication bytes.

**Statistics.** Each defense runs on 3 domains × 8 conditions × 10 seeds. Means carry
95 % bootstrap CIs over episodes. FL-DualGuard is compared with every other method
using paired Wilcoxon signed-rank tests on identical traffic, with Holm correction.
Benign-only episodes are reported separately to measure false-alarm cost.

## 8. Reproduce

```bash
python3 -m venv ~/.venvs/loft && source ~/.venvs/loft/bin/activate
pip install -r loft_project/requirements.txt
cd loft_project
python -m pytest -q tests
python -m loftbench.experiment --out results/v2 --stages collect,train,offline,export
python -m loftbench.tune --out results/v2          # validation-only knob selection
python -m loftbench.experiment --out results/v2 --stages online,report
```

Results, tables, and figures are written to `results/v2/`. Findings are summarized in
`docs/results_v2.md`.

## 9. Related work that bounds the novelty claim

- **SVM+RF for LOFT:** FTSheild (2025).
- **Federated low-rate and multi-controller detection:** Ali et al. (2023) and FedSec
  (2024).
- **ML LOFT detection with eviction or blacklisting:** FloRa (2024), FTMaster (2023),
  FTOP (2024), and DMS-BTT (2025).
- **Adaptive or dynamic idle timeouts for flow-table protection:** several earlier
  works. Survey and cite them before submission.

Do not claim novelty for any single ingredient. The defensible claim is the
measured effect of cross-domain federated knowledge combined with
budget-calibrated soft/hard mitigation on benign service under unseen variants.

## 10. Limitations

- The primary results come from simulation. The emulation harness must be run, and
  its no-defense and FL-DualGuard trends confirmed, before submission.
- The benign traffic is a parametric bigFlows-like model, not trace replay.
  Replaying `bigFlows.pcap` (or CAIDA/MAWI traces) is a recommended robustness check.
- Federated clients are honest. Poisoning, secure aggregation, and differential
  privacy are out of scope; raw-data locality is not a formal privacy guarantee.
- Labels for local training assume past incidents were forensically labeled.
