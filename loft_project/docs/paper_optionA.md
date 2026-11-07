# Federated Detection of Low-Rate Flow-Table Overflow: Generalization Across Controllers, and What a Real Testbed Changes

*Draft, 2026-11-07 (v5 results added). Paper direction "option A" (chosen by the author). Every number comes from a
committed results file, named in brackets; figures are in `results/paper_figs/`.
[cite] marks a missing reference; [TODO] marks open writing work. Authors and venue are
still to be filled in.*

---

## Abstract

**The attack.** A low-rate flow-table overflow (LOFT) attack fills an SDN switch's flow table
with rules that each stay just inside the idle timeout. New flows are then refused, and the
traffic stays below rate-based alarms.

**The gap.** Most defenses train a classifier per controller on attacks that controller has
seen. They are evaluated in Mininet against the same attack generator.

**What we study.** Two questions:
1. Does sharing models across controllers (federated detection) help a controller recognize
   attacks only others have seen, or that nobody has seen?
2. Do the conclusions survive a move from simulation to a real OpenFlow testbed?

**Method.**
- We reimplement the detectors of FTMaster, FTOP, FloRa and DMS-BTT on the same features and the
  same data.
- We compare them with two federated detectors: FL-DualGuard (an MLP) and EnsGuard (Random
  Forest plus CatBoost by model sharing).
- In a preregistered campaign of 200 runs on a Ryu/Open vSwitch testbed, we compare ten
  defenses, including EVICT, SIFT, TableGuard and rDefender.

**Findings.**
1. **Offline, federation helps exactly where it should.** At a 0.1 % benign false-positive
   rate:
   - On attacks seen only by another controller, EnsGuard keeps 98.7 % recall; the per-controller
     baselines drop to 79-82 %.
   - On an attack no controller saw, EnsGuard has the highest recall (48.5 %), against
     FL-DualGuard 34.4 % and 9.5-24.9 % for the baselines.
2. **On the testbed, the preregistered hypotheses mostly fail.**
   - EnsGuard keeps a lower attack share than EVICT, SIFT and TableGuard (14 of 15 paired runs
     each, Holm-adjusted p = 0.004).
   - It is not better than DMS-BTT, FTMaster, FTOP, rDefender or FL-DualGuard on benign harm or
     attack share.
   - It blocked a benign host in 4 of 20 runs.
3. **Testbed entry logs show why.**
   - The miss is not poll jitter and not a simulator-to-testbed gap: the simulator already
     predicts it.
   - The trace domain's benign traffic scores above the disguised attacks (A4, E9P). Every
     detector misses them in both settings.
   - Adding the trace controller as a federated client with one easy attack makes things worse:
     A4 recall stays 0 %, and unseen-attack recall falls to 14.9 %.
4. **A preregistered fix (v5) on a clean train/test split.** With every trace model trained on
   the first 40 % of the trace and 120 test runs on the rest, v5 (the federated CatBoost detector,
   a floored block rule and a detector-independent volume block) has the lowest mean benign harm
   (0.49 %, against DMS-BTT 1.71 % and FTMaster 4.80 %) and halves the attack share (21.9 %
   against 41.9-45.5 %). It wins on attack share against DMS-BTT (15 of 15 paired runs) and on
   harm, decision time and attack share against our earlier versions. It does not win on harm
   against DMS-BTT and FTMaster (10 of 15 each): under the standard attack A2 they are at about
   0 % and v5 at 1.05 %.

**Contributions.** A same-data detection benchmark; a preregistered testbed comparison; the
simulator-testbed comparison; and a documented negative result. We release code and data.

---

## 1. Introduction

**The attack.** SDN switches hold a bounded flow table. An attacker who keeps many rules alive at
low cost can fill it:
- one small packet per rule, sent just inside the idle timeout;
- benign flows that need a new rule are then refused or delayed [cite LOFT, Cao et al. 2017].

The attack is low-rate by construction, so rate-based DDoS defenses do not see it.

**The defense literature.** It has converged on one template
(`Other Paper/experiments_summary.md`, §13):
- a classifier per controller, over table- and rule-level features;
- evaluated in Mininet + Ryu + Open vSwitch, with a Scapy attacker parameterized by period, step
  and maximum rule count;
- reporting offline accuracy and online table metrics (attack-rule share, table usage, overflow
  time, Packet-In and Table-Full counts) [cite SFTO-Guard, FTMaster, FTODefender, FTOP, DMS-BTT,
  FloRa, FTShield].

**Three gaps in that template.**
1. *Generalization.* Detectors are trained and tested on the same attack parameters. DMS-BTT's
   mixed-parameter accuracy is only about 87 % [cite], and ALFO-Guard shows that the eviction
   policy changes how well FTMaster and LOFTGuard detect attacks [cite]. No paper tests attacks
   held out from training, or attacks seen by a different controller.
2. *Disguised and adaptive attacks.* Only rDefender (trace-replay attacks that look benign) and
   ALFO (an attack adapting to the eviction policy) test them. Both show that feature-based
   detectors degrade [cite].
3. *Real systems and harm to users.* Most results come from simulation and report table-level
   proxies. Few measure harm to benign users, such as lost first packets or failed new
   connections. rDefender is the exception for Packet-In loss [cite].

**Our questions.**
- **Q1 (offline):** with several controllers that each saw different attacks, does sharing
  models let one controller detect attacks it never trained on?
- **Q2 (testbed):** does a federated defense reduce benign harm and attack occupancy on a real
  OpenFlow controller, against eight published or classic defenses, under a preregistered
  analysis?
- **Q3 (gap):** when simulation and testbed disagree, what causes it?

**Contributions.**
1. **A same-data detection benchmark (E11).** It covers six detector families, with local and
   federated variants of each. All are trained and scored on identical rows and grouped by
   exposure: attacks seen locally, seen only remotely, or seen by nobody (§5).
2. **A preregistered testbed comparison** of ten defenses: 4 traffic types x 5 fresh seeds x 10
   defenses = 200 runs. It measures what users feel (benign flows harmed, lost first packets,
   new-connection success) next to the table metrics the related papers report (§6).
3. **A diagnosis of the simulator-testbed gap** from per-entry counter logs recorded on the
   testbed. The miss is domain shift, not poll jitter (§7).
4. **A preregistered negative result.** Adding the trace domain's controller to the federation,
   trained on its benign traffic plus one attack, fails every detection criterion fixed in
   advance (§8).
5. **A preregistered second campaign (v5)** on a clean train/test split of the trace, which
   closes most of the gap: much lower harm and attack share under the disguised attacks, and
   about equal to the best baselines under the standard attack (§9).
6. **Code, data and figures** in the style of the related papers (§13).

**What we do not claim.** EnsGuard v3 does not beat the modern ML defenses on the testbed (§6).
v5 beats them under the disguised attacks and on attack share, but not on harm under the
standard attack A2, and its gain on the disguised attacks comes largely from a rule that does
not use the detector (§9). We report where each version is better and where it is worse.

---

## 2. Background and threat model

**Switch model.**
- OpenFlow 1.3; a table of C = 3,500 rules; idle timeout 10 s.
- The controller installs a 5-tuple rule on each table miss (Packet-In) and polls flow
  statistics every 1 s.

**Attacker.** It follows the DMS-BTT recurrence N_i = N_{i-1} + S:
- every burst refreshes all its live rules and opens S new ones;
- the gap between bursts is drawn from a range below the idle timeout;
- it stops at M = 1,700 rules per attacker; two attackers per domain.

The variants used throughout are listed below (`loftbench/config.py`).

| Variant | S | Burst gap (s) | Packets per refresh | Packet size | Sources | Closest published attack |
|---|---|---|---|---|---|---|
| A1-A3 | 75 / 100 / 125 | 5.0-9.5 | 1 | 64 B | host or pool | DMS-BTT's three groups; the Tang et al. template |
| A2 | 100 | 5.5-9.0 | 1 | 64 B | own address | the standard LOFT attack |
| A4 (mimic) | 100 | 6.0-9.5 | 1-3 | benign-like | pool | rDefender's advanced low-rate attack (ALA) |
| A5 (spoof) | 100 | 5.5-9.0 | 1 | 64 B | spoofed | FTODefender's spoofed attackers |
| A6 (slow fill) | 45 | 8.0-9.8 | 1-2 | benign-like | spoofed | (held out from all training) |
| A7 (pulse) | 300 | 5.0-8.0, 60 s on / 30 s off | 1 | 64 B | host | |
| E9P (adaptive) | 100 | 2.0-3.0 | 1-3 | benign-like | pool | in the spirit of ALFO |

E9P is the best response of a search over attack parameters against six of our seven defenses
(`loftbench/e9_adaptive.py`).

**Defender and federation.**
- The defender sees only OpenFlow state.
- Controllers share trained models; they never share raw traffic.
- Poisoning by a malicious controller is out of scope.

---

## 3. Systems compared

### 3.1 Features

Every detector uses the same 17 causal features, computed per entry from counter deltas and the
controller's own poll history (`loftbench/features.py`, `FeatureTracker`).

- The baselines use the subsets their papers define:
  - FTMaster: 6 rule features;
  - FTOP: 4;
  - FloRa: 8;
  - DMS-BTT: (Numb, PIT, Sizep).
- The same extractor runs inside the Ryu application, and it is identical offline and on the
  testbed: both clocks match exactly (`testbed/check_entrylog.py`, parity check).

### 3.2 Detectors

| Detector | Model | Training | Source |
|---|---|---|---|
| FTMaster | XGBoost, rule features | local (per controller) | reimplemented [cite] |
| FTOP | Random Forest, rule features | local | reimplemented [cite] |
| FloRa | CatBoost, flow features | local | reimplemented [cite] |
| DMS-BTT | CatBoost state + flow models, two-level threshold | local | reimplemented [cite] |
| X@fed | each of the above, averaged over controllers | federated, for a fair test | ours |
| FL-DualGuard | MLP 17-32-1, FedAvg/FedProx | federated | our earlier system |
| EnsGuard | RF (50 trees, depth 12) + CatBoost, mean of the controllers' models | federated by model sharing | this paper |

Each controller calibrates its own threshold τ on its own validation benign traffic, at a
0.1 % benign budget.

### 3.3 EnsGuard's mitigation

At each 1 s poll, three steps run in order (`loftbench/evictblock.py`; selected on simulator
development seeds, `results/evictblock/selected.json`):

1. **Evict** every entry whose score is at least τ.
2. **Block a host** (by port and MAC) when two conditions hold:
   - its evictions in 10 s are at least 50;
   - they are at least 3 x the median host's.

   A block lasts 60 s at first and doubles on repeat, up to 240 s.
3. **PortGuard** (a weighted fair share per access port, mode "full") acts as the fallback when
   the table is still too full.

### 3.4 Mitigation baselines on the testbed

- **Classic:** EVICT, SIFT, TableGuard.
- **Published:** rDefender (port-occupancy anomaly + random deletion), FTMaster, FTOP and
  DMS-BTT, each with its paper's mitigation.
- **Ours:** FL-DualGuard with PortGuard and host identity.

All are reimplemented in one Ryu application (`testbed/loft_ryu_app.py`). [TODO: one paragraph
per baseline on the deviations from its paper.]

---

## 4. Experimental setup

### 4.1 Simulator and domains

**LOFT-Bench** is our discrete-time simulator of an OpenFlow table with idle expiry, refresh,
eviction and polling (`loftbench/sim.py`).

**Domains.**
- Three synthetic benign domains: D1 (enterprise), D2 (IoT, periodic hard negatives) and
  D3 (cloud, flash crowds).
- One trace domain, T1: bigFlows.pcap replayed as DMS-BTT does [cite].

**Attack exposure per controller:**

| Controller | Attacks in its training data |
|---|---|
| D1 | A1, A4 |
| D2 | A2, A5 |
| D3 | A3, A7 |

A6 is in no controller's training data. E9P is never trained on.

**Seed ranges** are disjoint:

| Use | Seeds |
|---|---|
| Training | 1000-1004 |
| Validation and selection | 2000-2002 |
| Offline test | 3000-3004 |
| Simulator online test | 26000-26004 (one shot) |
| Testbed test | 4120-4124 |
| Testbed recordings | 4131-4133 |

### 4.2 Testbed

**Hardware and software.** One 4-core laptop running Mininet, Open vSwitch and Ryu (OpenFlow 1.3).

**Topology (tree3).**
- A core switch s11 connects to the server.
- Two access switches, s12 and s13, each hold 3 hosts, one of which is an attacker.
- All three tables have 3,500 rules, idle timeout 10 s, and are monitored.

**Traffic.**
- Benign traffic is T1 (bigFlows), scaled to 0.5x. The scale was preregistered: it is the
  largest load at which a benign-only run loses at most 0.25 % of first packets and every probe
  succeeds (`results/testbed_prereg_v3/preregistration.json`).
- Each run lasts 300 s, with the attack starting at 50 s.
- A probe opens one new TCP connection every 0.5 s.

**Defenses.** One instance per switch, and one controller per run.

### 4.3 Metrics

**Harm to users (primary):**
- **benign flows harmed:** refused, dropped by a block rule, or with their first packet lost;
- **lost first packets** at the controller (rDefender's Packet-In loss);
- **new-connection success and connect time** (LOFT, ALFO).

**Table metrics, as in the related papers:**
- average and maximum attack-rule share Pa;
- average table usage;
- seconds at the limit after the attack starts;
- Packet-In and Table-Full counts;
- decision time per poll; controller CPU and memory.

**Detection:** accuracy, precision, recall, F1, false-positive rate, MCC, ROC-AUC and PR-AUC, at
the deployed threshold and at fixed benign false-positive rates.

### 4.4 Preregistration

Hypotheses, seeds, defenses, the model hashes and the test were fixed before any defense ran on
the test seeds (`results/testbed_prereg_v3/preregistration.json`).

- **H1:** EnsGuard harms fewer benign flows than each of the 8 comparators.
- **H2:** EnsGuard has a lower average attack share at s11 than each of the 8.
- **H3:** benign-only runs have mean harm of at most 0.5 % and lost first packets of at most 1 %.
- **H4:** no benign host is blocked in any EnsGuard run.

**Test.** For H1 and H2: a one-sided exact sign test over the 15 paired attack runs (A2, A4, E9P
x 5 seeds). A tie counts against the hypothesis. Holm correction over the 8 comparators,
α = 0.05.

---

## 5. Q1: offline detection that generalizes (E11)

**Setup.** Every detector is trained on the same rows (D1-D3 training seeds) and scored on the
same offline test rows (seeds 3000-3004). Results are grouped by exposure from the scoring
controller's point of view (`loftbench/e11_detect.py`, `results/e11_detect/table_main.csv`).

**Table 1.** Recall and PR-AUC (%) at a 0.1 % benign false-positive rate; the mean over
(controller, attack) cases.

| Detector | Recall, seen locally | Recall, seen by another | Recall, seen by none | PR-AUC, seen by none |
|---|---|---|---|---|
| FTOP | 92.0 | 79.4 | 9.5 | 42.2 |
| FTMaster | 92.4 | 81.3 | 15.0 | 43.6 |
| FloRa | 97.5 | 82.2 | 24.9 | 55.0 |
| DMS-BTT | 92.3 | 81.6 | 14.3 | 39.6 |
| FTOP@fed | 82.9 | 82.7 | 1.5 | 73.3 |
| FTMaster@fed | 83.0 | 87.3 | 12.8 | 74.4 |
| FloRa@fed | 83.0 | 90.3 | 24.8 | 91.8 |
| DMS-BTT@fed | 83.0 | 86.9 | 12.6 | 73.4 |
| FL-DualGuard | 97.4 | 96.7 | 34.4 | **93.3** |
| **EnsGuard** | **99.2** | **98.7** | **48.5** | 92.7 |

**Findings.**
- **Seen locally:** every detector reaches 92-99 % recall. This matches the related papers'
  offline numbers: FTMaster reports 99.3 % accuracy, FTOP 98.7 %, FloRa 99.5 % [cite].
- **Seen only by another controller:** the local baselines drop to 79-82 %. The two federated
  detectors keep 97-99 %. Averaging the baselines' probabilities (@fed) recovers part of the
  drop (83-90 %), but it costs them recall on attacks they saw locally (about 83 %).
- **Seen by no controller (A6):** EnsGuard has the highest recall, 48.5 %. FL-DualGuard follows
  at 34.4 %, and the others are at most 24.9 %. FL-DualGuard has the best PR-AUC (93.3 against
  92.7), so the two federated detectors rank attacks about equally well. EnsGuard's threshold
  keeps more of them above it.
- **Figure 9** (`fig09_classifier_comparison`) shows accuracy, precision, recall and F1 per
  exposure, in the layout of the related papers' classifier comparisons.

**Cost of the ensemble** (`results/e1_pair/cost.csv`; E1, 1 % budget):

| Model | Scoring time per 10,000 entries | Size per controller | F1 on unseen attacks |
|---|---|---|---|
| RF (50 trees, depth 12) | 71.8 ms | 3.7 MB | 77.3 |
| CatBoost | 18.9 ms | 0.3 MB | 84.0 |
| RF + CatBoost | 90.7 ms | 4.0 MB | 84.3 |

- The RF is about 80 % of EnsGuard's scoring cost and adds little to CatBoost's generalization.
  We return to this cost in §6, §9 and §10.
- Model sharing is a one-time transfer of about 4 MB per controller. FL-DualGuard instead
  exchanges 370 kB over 30 rounds (`results/e10_overhead/fl_comm.json`).

**Simulator online test** (fresh seeds 26000-26004, D1-D3, run once;
`results/evictblock/test_summary.csv`).

| Variant | EnsGuard harm | EnsGuard attack occupancy | Comparison |
|---|---|---|---|
| A2 | 0.36 % | 2.0 % | |
| A4 | 0.73 % | 5.0 % | DMS-BTT with blocklist: harm 20.5 %, occupancy 39.3 % |
| A6 | 0.37 % | 5.3 % | |
| E9P | 2.0 % | 26.2 % | FL-DualGuard: harm 1.1 % |
| benign | 0.08 % | n/a | |

- No benign host was blocked.
- Without PortGuard, E9P harm rises to 37.7 %. PortGuard carries the adaptive case.
- In simulation, EnsGuard is the best system we have.

---

## 6. Q2: the preregistered testbed comparison

All numbers are means over 5 seeds (`results/testbed_prereg_v3/report.md`,
`results/paper_figs/testbed_runs.csv`).

### 6.1 Hypotheses

**H1: lower benign harm. Not supported** against any comparator. EnsGuard's mean harm is
3.76 %.

| Comparator | Comparator mean harm | EnsGuard wins / 15 | Holm-adjusted p |
|---|---|---|---|
| DMS-BTT | 3.31 % | 6 | 1.00 |
| FL-DualGuard | 4.06 % | 9 | 1.00 |
| FTMaster | 4.60 % | 7 | 1.00 |
| FTOP | 5.14 % | 9 | 1.00 |
| EVICT | 5.19 % | 10 | 0.75 |
| rDefender | 6.16 % | 11 | 0.41 |
| TableGuard | 8.93 % | 11 | 0.41 |
| SIFT | 9.49 % | 12 | 0.14 |

**H2: lower attack share at s11. Supported against the classic defenses only.** EnsGuard's mean
share is 41.2 %.

| Comparator | Comparator mean share | EnsGuard wins / 15 | Holm-adjusted p | Supported |
|---|---|---|---|---|
| EVICT | 60.9 % | 14 | 0.004 | yes |
| SIFT | 53.5 % | 14 | 0.004 | yes |
| TableGuard | 56.1 % | 14 | 0.004 | yes |
| FL-DualGuard | 46.7 % | 11 | 0.30 | no |
| FTOP | 43.5 % | 6 | 1.00 | no |
| rDefender | 42.0 % | 7 | 1.00 | no |
| FTMaster | 41.2 % | 9 | 1.00 | no |
| DMS-BTT | 39.9 % | 5 | 1.00 | no |

**H3: benign-only runs stay clean. Passes.** Harm 0.00 %, lost first packets 0.04 %.

**H4: no benign host blocked. Fails.** A benign host was blocked in 4 of EnsGuard's 20 runs.

### 6.2 Table metrics in the related papers' format

**Table 3** (`results/paper_figs/comparison_table.csv`, Fig. 3). Means over A2, A4 and E9P x 5
seeds at s11.

| Defense | Avg Pa % | Max Pa % | Avg usage % | Seconds at limit | Packet-In (k) | Table-Full |
|---|---|---|---|---|---|---|
| None | 58.7 | 92.2 | 77.8 | 47.3 | 70.3 | 2,998 |
| EVICT | 60.9 | 90.1 | 80.1 | 74.1 | 61.7 | 0 (evicts) |
| SIFT | 53.5 | 88.8 | 72.5 | 30.2 | 71.1 | 1,724 |
| TableGuard | 56.1 | 88.1 | 74.8 | 27.7 | 67.8 | 1,614 |
| rDefender | 42.0 | 89.3 | 62.7 | 11.9 | 80.4 | 813 |
| FTMaster | 41.2 | 78.5 | 60.4 | 25.1 | 77.8 | 1,299 |
| FTOP | 43.5 | 85.7 | 63.1 | 8.9 | 71.0 | 498 |
| DMS-BTT | **39.9** | **76.2** | 60.5 | 4.4 | 77.5 | 225 |
| FL-DualGuard | 46.7 | 76.9 | 65.8 | **1.7** | 71.3 | **77** |
| EnsGuard | 41.2 | 82.1 | **60.5** | 5.3 | **61.3** | 332 |

- **Rule share and occupancy over time** (Figs. 1-2) follow the same pattern.
  - Against A2, FTMaster and EnsGuard remove the attacker for long stretches; DMS-BTT and FTOP
    only reduce it.
  - Against A4 and E9P, the attack share climbs to 70-90 % under most defenses. DMS-BTT, FTOP and
    rDefender pull it down to about 50 % for parts of the run.
- **Table composition 150 s into A4** (Fig. 10). With rDefender, the table is 33 % attack, 10 %
  benign and 57 % free. With EnsGuard it is 70 / 17 / 13.

### 6.3 Results per attack

**Table 4.** Means over 5 seeds.

| Attack | Measure | EnsGuard | Best other defense |
|---|---|---|---|
| A2 | attack share | 15.1 % | FTMaster 10.1 % |
| A2 | benign harm | 2.78 % | FTMaster 0.04 %, DMS-BTT 0.06 % |
| A2 | new connections succeeding | **37.6 %** | rDefender 33.5 % |
| A4 | attack share | 47.4 % | rDefender 41.7 % |
| A4 | benign harm | 7.6 % | EVICT 4.3 % |
| A4 | lost first packets | 25.0 % (worst) | rDefender 14.5 % |
| E9P | attack share | 61.0 % | rDefender 47.3 % |
| E9P | benign harm | **0.9 %** | FL-DualGuard 4.4 % |
| E9P | lost first packets | 47.8 % (worst) | rDefender 27.6 % |
| E9P | Packet-In (k) | **52.5** | EVICT 60.0 |

### 6.4 Where EnsGuard is better, and where it is worse

**Better:**
- lower attack share than the classic defenses (H2);
- the fewest Packet-Ins under A4 and E9P, and overall (Figs. 3-4);
- the lowest benign harm under E9P;
- the most successful new connections under A2 (Fig. 6);
- the second-fewest seconds at the limit and Table-Full messages under A4 and E9P;
- clean benign-only runs (H3).

**Worse:**
- no significant win over any modern ML defense (H1, H2);
- higher harm than FTMaster and DMS-BTT under A2, and high harm under A4 (7.6 %, against 8.6 %
  with no defense);
- the most lost first packets under A4 and E9P;
- the slowest scoring: median 160 ms per poll under A4 and 232 ms under E9P (Fig. 7);
- the most memory, about 300-325 MB (Fig. 8);
- benign hosts blocked (H4).

**Overhead.** Every defense runs the controller at about 93 % of one core under attack
(Fig. 8). The controller is saturated, and this affects all defenses
(`results/testbed_prereg_v3/posthoc_diagnosis.md`). Under saturation, slow scoring turns
directly into lost first packets. This explains why EnsGuard loses the most first packets even
where it has the fewest Packet-Ins.

---

## 7. Q3: why the testbed disagrees with the simulator

The analysis in this section is exploratory (post hoc). It is kept separate from the
preregistered results.

### 7.1 Instrumentation

**Recording.** The Ryu application logs every entry's counters at every poll
(`LOFT_ENTRYLOG`). Writing the log costs 0.17 ms per poll for 3,500 entries.

**Recordings.** 12 runs: A2, A4, E9P and benign x seeds 4131-4133, with no defense.
- The smoke run's harm and load match the v3 "none" runs, so the logging is not visible in the
  results.
- 95-99 % of the logged flows match a ground-truth label.

**Rebuilding features offline.** `testbed/entrylog.py` rebuilds the 17 features with the
controller's own tracker on two clocks:
- the real poll times ("wall");
- a warped clock with polls exactly 1 s apart ("poll"), which removes jitter.

**Scoring.** Every detector is scored on the same recorded rows and on simulator T1 rows with
the same attacks and seeds (`testbed/e11_testbed.py`, `results/e11_testbed/report.md`).

### 7.2 Findings

1. **The testbed reproduces the simulator.** At the simulator's 0.1 % threshold:
   - every detector catches A2: simulator 81-99 %, testbed 49-95 % (EnsGuard 99.5 % and 95.1 %);
   - every detector misses A4 and E9P, at most 1.3 % recall, in both settings.
2. **The simulator already predicts the miss.** On T1 validation traffic, the 99.9th percentile
   of benign scores (0.67) lies above the median A4 score (0.34). Fig. 11 shows the same picture
   on the testbed recordings:
   - median attack scores: A2 0.86, A4 0.26, E9P 0.05;
   - deployed threshold: 0.64.

   On D1, whose controller trained on A4, the same detector catches 96.6 % of A4. The cause is
   domain shift between the synthetic domains and the trace's benign traffic. It is not a defect
   of the testbed.
3. **Ranking survives; thresholds do not.**
   - On the testbed, A4 PR-AUC is about 89 for EnsGuard, DMS-BTT@fed and FTOP@fed (simulator
     93-96). Attack entries do rank high, but below the trace's benign tail.
   - FL-DualGuard's false-positive rate rises from 0.3 % in the simulator to 4-10 % on the
     testbed.
   - Benign traffic during an attack scores higher than benign traffic alone. A threshold set on
     the testbed's benign-only runs gives EnsGuard a 0.6-1.0 % false-positive rate in attack
     runs.
4. **Poll jitter is not the cause.**
   - Wall-clock and warped-clock features give similar recall.
   - A2 recall does not fall for long poll gaps; it rises slightly.
5. **Mitigation on the testbed is done mostly by PortGuard.** EnsGuard's detector barely fires
   under A4 and E9P, so attacker removal falls to the fair-share fallback.
   - The block rule's median degenerates to 0, so it blocks busy benign hosts. This is the H4
     failure.
   - Controller overload (stretched polls; 6-48 % of first packets lost) hits every defense, and
     it hits EnsGuard hardest because its scoring is slowest.

---

## 8. A preregistered negative result: the trace controller joins the federation

**Hypothesis.** If the miss is domain shift, then giving the trace domain's controller (T1) a
local model trained on its own benign traffic should fix it.

**Design.**
- T1's model is trained on T1 benign traffic plus A2, the standard attack it would plausibly have
  seen. It never sees A4 or E9P.
- It is shared like the others, making 8 models.
- Every controller recalibrates τ.

**Decision rules.** Fixed before training (`docs/v4_plan.md`):

| ID | Condition | Bar |
|---|---|---|
| R1 | A4 recall on T1, in the simulator and on the testbed | at least 30 % |
| R2 | Benign false-positive rate | at most 0.5 % |
| R3 | A2 recall | no more than 2 points below v3 |
| R4 | Recall on attacks no controller saw, D1-D3 | at least 46.5 % |

**Result** (`results/v4/check.md`):

| Detector | A4 recall, simulator / testbed | Recall on unseen attacks (E11) | Pass |
|---|---|---|---|
| v3 (D1-D3) | 0.0 / 0.0 | 48.5 | no |
| v4 (T1 joins, RF + CatBoost) | 0.0 / 0.0 | 14.9 | no |
| v4, CatBoost only | 0.0 / 0.0 | 21.0 | no |

R2 and R3 pass for every detector.

**Why it fails.**
- T1's threshold falls from 0.64 to 0.48, but A4's median score falls too: from 0.34 to 0.25 in
  the simulator, and from 0.26 to 0.20 on the testbed. T1's model learns that only A2's fixed,
  tiny refresh pattern is an attack, so its vote pushes the mimicry attack toward benign.
- Under averaging, one client that knows a single easy attack dilutes what the others learned.
  On D1, unseen-attack recall falls from 45.9 % to 0.2 %.

**Lesson for federated LOFT detection.** Adding a client is not free. A client's attack exposure
matters as much as its benign data. Simple model averaging gives a narrowly trained client a full
vote. As fixed in advance, we stopped here: no retuning on these data, and no testbed campaign
for this detector.

---

## 9. v5: a preregistered fix on a clean train/test split

§6-§8 leave two problems: the trace-domain models of every defense had seen the test traffic
(each seed replays the same 5-minute capture), and no detector catches A4 or E9P on that trace.
v5 addresses both without touching the federated detector's training data.

### 9.1 Design (fixed before any v5 test run; `docs/v4lite_plan.md`, `docs/v5_plan.md`)

- **Clean split.** The trace is split into T1A (the first 40 % of its span) and T1B (the last
  60 %). A flow belongs to the part holding its first packet, so the parts share no flow. Every
  T1 model and threshold, ours and the baselines' (DMS-BTT, FTMaster), is trained or calibrated
  on T1A; all v5 test runs replay T1B.
- **Detector (v4-lite):** the D1-D3 CatBoost members of v3 only. Offline it generalizes as well
  as RF + CatBoost at about 1/5 of the scoring cost. Scoring uses an exact 8-bit oblivious-tree
  evaluator, and only entries whose counters changed since the last poll are scored.
- **Floored block rule (v4-lite):** a host is blocked when its evictions in 10 s are at least
  3 x max(median host, 10) and at least 20 % of its own entries.
- **Volume block (v5):** while the table is at least 90 % full, a host holding more than X
  entries and at least 3 x the median host's is blocked. X is 1.5 x the busiest benign host in
  T1A testbed recordings (785-800 per switch). It was adopted by a rule fixed in advance: in an
  open-loop replay of 6 T1A recordings it blocks no benign host and both attackers under A2, A4
  and E9P (`results/v5/volume.md`).
- **Not adopted:** a local T1A model (+0.5 points of A2 recall, within the tie margin) and a univ2
  client in the federation, which cut unseen-attack recall from 51.0 % to 8.6 %, the dilution of
  §8 again (`results/v5/cands.md`).

### 9.2 Preregistered campaign

Six defenses (none, EnsGuard v3, v4-lite, v5, DMS-BTT, FTMaster) x A2, A4, E9P and benign x
fresh seeds 4140-4144 = 120 runs on T1B, otherwise as §4.2. The hypotheses, seeds and analysis
script were committed before the first test run (`results/testbed_prereg_v5/preregistration.json`).
One run (v4-lite, E9P, seed 4142) ended early and was rerun once with the same seed, as
preregistered. Tests: one-sided exact sign test over the 15 paired attack runs, ties count
against, Holm over the comparators of each hypothesis.

**Table 6** (`results/testbed_prereg_v5/report.md`).

| Hypothesis | Comparator | v5 wins / 15 | v5 mean | Comparator mean | p (Holm) | Supported |
|---|---|---|---|---|---|---|
| H1 benign harm | DMS-BTT | 10 | 0.49 % | 1.71 % | 0.30 | no |
| H1 benign harm | FTMaster | 10 | 0.49 % | 4.80 % | 0.30 | no |
| H2 attack share s11 | DMS-BTT | 15 | 21.9 % | 41.9 % | 0.0001 | **yes** |
| H2 attack share s11 | FTMaster | 11 | 21.9 % | 45.5 % | 0.059 | no |
| H3 benign harm | v3 | 12 | 0.49 % | 3.48 % | 0.018 | **yes** |
| H4 decision time per poll | v3 | 12 | 54 ms | 127 ms | 0.018 | **yes** |
| H8 attack share s11 | v4-lite | 12 | 21.9 % | 43.4 % | 0.018 | **yes** |

- **H5, no benign host blocked by v5:** passes (0 of 20 runs; v3 blocked 6 in the same campaign).
- **H6, benign-only runs clean:** passes (harm 0.00 %, lost first packets 0.12 %).
- **H7, new-connection success not more than 5 points below v3:** passes (0 of 15 pairs).

### 9.3 Per attack

**Table 7.** Means over 5 seeds (`results/paper_figs/v5/testbed_runs.csv`, Fig. 15).

| Attack | Measure | v3 | v4-lite | v5 | DMS-BTT | FTMaster |
|---|---|---|---|---|---|---|
| A2 | benign harm | 2.64 % | 0.13 % | 1.05 % | 0.02 % | **0.01 %** |
| A2 | attack share s11 | 12.2 % | 11.9 % | 12.6 % | 18.7 % | **10.0 %** |
| A4 | benign harm | 5.59 % | 1.68 % | **0.32 %** | 2.09 % | 4.16 % |
| A4 | attack share s11 | 47.0 % | 50.9 % | **27.2 %** | 47.6 % | 53.4 % |
| E9P | benign harm | 2.21 % | 2.97 % | **0.10 %** | 3.01 % | 10.22 % |
| E9P | attack share s11 | 66.1 % | 67.4 % | **26.0 %** | 59.3 % | 73.3 % |
| all | lost first packets | 34.3 % | 30.5 % | **19.8 %** | 32.6 % | 27.8 % |
| all | median decision time per poll | 123 ms | 45 ms | **13 ms** | 65 ms | 72 ms |

- **A4 and E9P.** v5 has lower harm than both baselines in every seed. v5 blocks both attackers in
  all 15 attack runs; neither baseline blocks an attacker. The gain comes from the volume block:
  v4-lite, with the same detector and no volume rule, blocks no attacker under A4 or E9P (H8).
- **A2.** The baselines' harm is about 0 % in every seed; v5 is at about 1 % in four seeds and
  0.02 % in one. This decides H1. Fig. 16 shows the mechanism: v5 blocks both attackers about
  70 s into the attack; the 60 s block expires; the returning attackers fill the table during a
  controller overload (event queue at its limit, decisions about 1 s) before the re-block, and
  benign flows are refused. In both A2 runs inspected, the table was never full before the first
  block expired (exploratory). DMS-BTT and FTMaster, trained on A2 traffic from the same network
  (T1A), delete attack entries every poll and keep the table below 2,800 entries.
- **New users.** Under attack only 12-47 % of new connections succeed with any defense; v5 is best
  under A2 (47 %) and level with the others under A4 and E9P. The saturated controller, not the
  table, limits them (§6.4).

**Exploratory, not preregistered** (`results/testbed_prereg_v5/exploratory_close.md`): paired by
seed, v5 minus baseline harm under A2 is +0.02 to +1.78 points; under A4 -0.03 to -5.39 points;
under E9P -1.23 to -12.57 points.

### 9.4 What v5 does and does not show

- On traffic no model was trained on, a federated detector plus a detector-independent volume
  rule beats the per-flow baselines on the disguised attacks and on attack share, and it is the
  only defense that removes the attacker. On the standard attack the baselines, trained on that
  attack in that network, remain slightly better on harm.
- The volume rule likely carries most of the A4/E9P gain. A volume-only ablation has not been run;
  an open-loop replay of the v5 recordings suggests it would block the attackers 100-175 s after
  the attack starts with no benign block, later than v5 under A2 (about 70 s) [TODO: closed-loop
  ablation, preregistered].
- An attacker that keeps each host below X per switch is not volume-blocked [TODO: adaptive
  attacker test].

---

## 10. Discussion

**What the evidence supports.**
1. Federated detection generalizes offline to attacks that other controllers saw, and better
   than any per-controller detector to attacks nobody saw (§5).
2. On a real controller under the trace domain, federation does not deliver a better defense
   than the best published per-controller systems (§6).
3. The reason is domain shift that the simulator already shows, not testbed artifacts (§7).
4. Naively adding the trace domain as a client makes things worse (§8).
5. With a clean split, a detector-independent volume rule added to the federated detector makes
   the defense better than the per-flow baselines under disguised attacks, and about equal under
   the standard attack (§9).

**Implications for the field.**
- *Report exposure.* "Accuracy 99 %" on attack parameters seen in training says little about
  attacks seen elsewhere (79-82 % recall) or seen nowhere (at most 25 %) (Table 1).
- *Test disguised attacks.* Every detector we tested, ours and the reimplemented published ones,
  fails on A4 and E9P on the trace domain. Only rDefender and ALFO test such attacks [cite]; our
  results agree with theirs.
- *Measure harm to users, and controller load.* Under saturation, a defense's own processing time
  shows up as lost first packets. This is invisible in Pa and Table-Full counts, and it changes
  the ranking (Table 4).
- *Weight clients by exposure, not by count.* §8 suggests exposure-aware aggregation, or local
  personalization (a local combiner over the shared models' scores), as the next step.
  [TODO: one or two sentences of related federated-learning work, cite.]

**Cheaper scoring.** CatBoost alone keeps almost all of the ensemble's generalization at about
1/5 of the scoring cost (§5). On the testbed, with changed-entry scoring, it cut the median
decision time from 123 ms to 13 ms and lost first packets from 34 % to 20 % (§9, H4).

**Blocks should outlast the attacker.** All of v5's A2 harm occurred after a 60 s block expired.
Holding a block while the blocked host keeps sending (visible in the drop rule's counter) is the
obvious next step; it needs its own preregistered test.

---

## 11. Limitations

- **One laptop, one controller.** The testbed saturates one Ryu process under attack. Results on
  multi-core or hardware switches may differ: LOFT, rDefender and FTShield use hardware [cite].
- **One trace domain on the testbed** (T1, bigFlows at 0.5x). The synthetic domains D1-D3 are
  evaluated only in the simulator.
- **Reimplemented baselines.** They follow each paper's features and algorithms, with the
  deviations listed in §3.4 [TODO]. Absolute numbers are not comparable with the papers' own
  results; each paper also re-runs its baselines under its own setup
  (`experiments_summary.md`, §13).
- **Generated attacks.** All attacks come from our generator. E9P is adaptive only against our
  defenses' parameter space.
- **Five test seeds per cell.** This gives modest power for paired sign tests: 12 of 15 wins are
  needed for an unadjusted p < 0.05.
- **Post-hoc analyses.** §7, the per-attack breakdowns in §6.3 and §9.3, and the A2 mechanism
  in §9.3 are exploratory. Only §6.1, §8 and §9.2 are preregistered.
- **Untested reviewer questions for v5:** a volume-only ablation and an attacker that stays below
  the volume limit (§9.4).
- **Threat model.** Federated poisoning and privacy attacks on shared models are out of scope.

---

## 12. Related work

[TODO: expand with full citations. One paragraph each.]

- **The attack:** LOFT [Cao et al., SecureComm 2017]; adaptive overflow, ALFO [Zeng et al.,
  IEEE Access 2024].
- **Eviction and table management:** EVICT, SIFT, TableGuard, FTGuard [cite]; rDefender
  [Kong et al., TIFS 2024].
- **ML detection and mitigation (Tang et al. template):** SFTO-Guard (JNCA 2023), FTMaster
  (TNSM 2023), FTODefender (ESWA 2024), FTOP (TNSE 2024), DMS-BTT (ESWA 2025).
- **Others:** FloRa (TNSM 2024, Raspberry Pi testbed); FTShield (ESWA 2025, Tofino P4).
- **Federated learning for SDN security** [cite 2-3 works].

---

## 13. Artifact

| Item | Location |
|---|---|
| Simulator and detectors | `loftbench/` |
| Ryu application and testbed scripts | `testbed/` |
| Preregistrations and reports | `results/testbed_prereg_v3/`, `results/testbed_prereg_v5/`, `docs/v4_plan.md`, `docs/v5_plan.md` |
| Detection benchmarks | `results/e11_detect/`, `results/e11_testbed/` |
| v4 negative result | `results/v4/` |
| v4-lite and v5 selection | `results/v4lite/`, `results/v5/` |
| Figures | `results/paper_figs/` (v3 campaign) and `results/paper_figs/v5/` (rebuilt by `testbed/paper_figs.py [--v5]`) |

[TODO: the testbed run directories, about 3.6 GB, need a data archive.]

---

## Figure and table plan

| Item | Content | Source |
|---|---|---|
| Fig. 1 | System overview: controllers share models; evict, block, fair share | `docs/ensguard_architecture.png` [TODO: update for option A] |
| Fig. 2 | Testbed topology (tree3) | `docs/ensguard_network.png` |
| Table 1 | E11 recall and PR-AUC by exposure | §5 |
| Fig. 3 | E11 classifier comparison | `fig09_classifier_comparison` |
| Table 2 | Preregistered H1-H4 | §6.1 |
| Table 3 | Testbed comparison in the related papers' format | §6.2, `fig03_comparison` |
| Fig. 4 | Rules over time, per defense (A4; A2 and E9P in the appendix) | `fig01_*` |
| Fig. 5 | Attack share over time | `fig02` |
| Fig. 6 | Harm and lost first packets; new-connection service | `fig05`, `fig06` |
| Fig. 7 | Score distribution on testbed recordings | `fig11` |
| Table 4 | Per-attack results | §6.3 |
| Table 5 | v4 negative result | §8 |
| Table 6 | v5 preregistered hypotheses | §9.2 |
| Table 7 | v5 per attack | §9.3 |
| Fig. 8 | v5 per attack and per seed | `v5/fig15_per_attack_per_seed` |
| Fig. 9 | v5 A2 block expiry | `v5/fig16_a2_block_expiry` |
| Fig. 10 | v5 comparison in the related papers' format; attack share over time | `v5/fig03_comparison`, `v5/fig02_attack_share_over_time` |
| Appendix | Packet-In over time, decision time, CPU and memory, table composition, block-rule sensitivity | `fig04`, `fig07`, `fig08`, `fig10`, `fig12` |
