# Final testbed campaign: preregistration

*Draft 2, 8 November 2026. Not yet fixed: it is fixed (hashed, results/testbed_prereg_final/
preregistration.json) after the user's approval and before any run on seeds 4160-4164. No run on
these seeds exists (checked in ~/loft-runs, 8 November). Draft 2 revises draft 1 (commit c9ac300)
after a critical review: data-matched baselines, held-out cells, a service hypothesis, per-attack
results with Holm over all tests, and the scope of the federated claim.*

## 1. The system under test

FEVER as frozen by the deployment check (docs/testbed_training_plan.md, amendment 1;
results/tbfl/flcheck.md):

- Detector: lossless federated XGBoost (three controllers, histogram sums, 300 trees), trained on
  the testbed recordings of C1-C3 (seeds 4170-4172); controller config
  results/v21/exported/ens_config_fl_ll.json, T1B threshold 0.4953 (0.1 % of the T1A benign rows
  of seeds 4173-4175).
- Response: v6's evict-block layer (rule A: n_min 50, frac_min 0.2, k 3; volume rule at 1.5 times
  the busiest benign host per switch, calibrated on T1A benign runs; permanent blocks), host
  identity on the tree, drop rules for blocked hosts.
- No PortGuard (results/tbfl/flcheck_pg.md).
- Controller defense name: fever-fl-ll. Nothing in it is changed after this document is fixed.

What FEVER's development has already seen, stated so that held-out claims are read correctly: the
attacks A2, A4 (Mimic) and E9P (Aware), the capture bigFlows (T1A and T1B), and the tree topology,
over the v3-v6 campaigns and the deployment check (seeds 4140-4144, 4181-4182). Fresh seeds give
fresh randomness on these cells, not fresh conditions. Section 5 names the cells that are held out.

## 2. Testbed

As in every campaign since v5: Mininet tree (core s11, access s12, s13), Open vSwitch, one Ryu
controller, table capacity 3,500, idle timeout 10 s, 1 s polls, 4 benign hosts and 2 attackers,
300 s runs, attack from 50 s, new-flow probe on (testbed/matrix_e5.sh, E5_TOPO=tree3). Traces:
bigFlows T1B at 600 pps (benign scale 0.5) and univ2 part 6 (UHt) at 1,000 pps. Mains power only.

## 3. Methods

| Name | Defense | Detector training |
|---|---|---|
| none | no defense | - |
| FTMaster | ftmaster | C3's rows (section 4) |
| FTOP | ftop | C3's rows |
| FTODefender | ftodefender | C3's rows |
| FloRa | flora | C3's rows |
| DMS-BTT | dms-btt (as published) | C3's rows |
| rDefender | rdefender | no learned model |
| FEVER | fever-fl-ll | section 1 |

**Data-matched baselines (fix 1).** FEVER's detector learns from three networks' rows; each
baseline above, as in its paper, from one. So that a win of FEVER cannot be put down to more data,
each learned baseline is also trained on the pooled rows of C1-C3 (the same rows FEVER's
federated training uses, raw rows shared, no privacy): ftmaster-pool, ftop-pool, ftodefender-pool,
flora-pool, dms-btt-pool. Lossless federated XGBoost gives the model that pooled XGBoost training
would give, so these runs compare methods on equal data.

**Ablations** (FEVER with one part removed, everything else unchanged):

| Name | Defense | Change |
|---|---|---|
| FEVER without sharing | fever-ll-local | XGBoost on C3's rows only, the lossless model's settings (300 trees, same parameters), threshold by the same rule |
| FEVER without the volume rule | fever-ll-novol | volume rule off |
| FEVER without the detector | fever-noml | no detector: volume rule only |

## 4. Baselines retrained on the testbed (before the campaign)

Each baseline is trained with its own features and model as implemented in loftbench, from the
entry logs: on C3's network (T1A, seeds 4170-4172) for the main arm, on C1-C3 pooled (seeds
4170-4172) for the data-matched arm. Each threshold or knob its paper sets on validation data is
set on the T1A benign recordings of seeds 4173-4175. Features the entry logs do not carry are
listed per baseline in results/testbed_baselines_tb/gaps.md, with the deviation from the paper.

**Source blocks in the switch (fixed 9 November 2026).** FTMaster, FloRa and FTODefender block a
source IP by installing a drop rule ("add-flows <src-dst tuple> action = drop" in FTMaster; an
ovs-ofctl flow rule in FTODefender; FloRa's controller "blocks the corresponding IPs"). Until 9
November our testbed versions refused a blocked source in the controller only, so each of its
packets still reached the controller as a Packet-In; this was weaker than the papers and cost the
baselines most under Aware, where the controller is the bottleneck. From now on (LOFT_DROP_RULES=1,
the default) each switch whose baseline blocks a source installs a permanent drop rule on that
source IP, above the per-flow rules, re-sent at the next poll if the switch refuses it as table
full. The papers give neither a timeout nor a switch; ours is permanent and on the switch that
decided, as FEVER's blocks. Earlier baseline runs (v5 campaign, results/tbfl/compare_baselines_dev.md)
used the controller-only refusal and are not compared with the campaign's. DMS-BTT's per-flow
blocklist is ours, not the paper's, and stays in the controller; FTOP and rDefender do not block.

Fidelity, before the campaign, in results/testbed_baselines_tb/fidelity.md:
- Against the paper: each baseline's headline result under its paper's own setting (attack share,
  recall or Packet-In loss, as the paper reports it) beside the published number, from the T1B test
  recordings (seeds 4176-4178) and the gate G1 results.
- Against our earlier model: a retrained baseline replaces its simulator-trained model only if its
  recall on the standard attacks (G1-G3, Spoof, Pulse) is at least that model's minus 5 points, at
  false alarms at most 1 %; otherwise the earlier model is kept and the reason reported. This
  keeps the better of two models for each baseline, which favours the baselines, and is stated.

## 5. Runs

Seeds 4160-4164, never used on the testbed. Five seeds where the claims rest (Mimic, Aware and the
held-out attacks), three (4160-4162) elsewhere.

| Block | Trace | Traffic | Methods | Seeds | Runs |
|---|---|---|---|---|---|
| Main | T1B | A2, A5 (Spoof), A7 (Pulse), benign | 8 | 3 | 96 |
| Main | T1B | A4 (Mimic), E9P (Aware) | 8 | 5 | 80 |
| Held out | T1B | A6 (Slow), EVX (volume-evading) | 8 | 5 | 80 |
| Data-matched | T1B | A4, E9P, A6, EVX | 5 pooled baselines | 5 | 100 |
| Ablations | T1B | A2 (3 seeds), A4, E9P (5 seeds) | 3 | 3 / 5 | 39 |
| Held-out trace | UHt | A2, A4, E9P, benign | none, FTMaster, DMS-BTT, rDefender, FEVER | 3 | 60 |
| 600 s check | T1B | A4, E9P | FEVER, DMS-BTT, FTMaster | 4160 | 6 |
| | | | | | **461** |

About 42 h (5.4 min per 300 s run, 10.5 min per 600 s run), one at a time, over five or six nights. Priority if time runs
short, fixed now: cut UHt benign, then the UHt block, then the ablations without the volume rule
and without the detector (their v5 counterparts exist); Main, Held out and Data-matched are never
cut.

**Held-out cells.** No part of FEVER was designed or tuned on them:
- A6 (Slow): seen by no controller in training and never used in FEVER's development.
- EVX (volume-evading, new): each attacker knows FEVER's volume limit and keeps at most 0.8 times
  the lowest per-switch limit of live entries at any time (628 entries on T1B), refreshing them
  before the idle timeout, at A2's sending rate otherwise. It tests the volume rule's known
  weakness with two attackers; more colluding attackers are the scalability study's subject
  (week of 23 November) and are not claimed here.
- UHt: univ2 part 6, a part of univ2 that no controller trained on (C1 and C2 trained on parts 0
  and 3, so the capture is not new; stated as such). Every method whose paper sets a threshold on
  benign traffic, FEVER included (tau and the volume limit), recalibrates it on the benign UHt
  recording tbt_UHt_benign_none_s4190 by its own rule; nothing is retrained.

Before the campaign, one smoke run per new or retrained defense and for EVX on development seed
4183 (A2, or EVX), which checks that it loads, blocks and logs; not results.

Order: by seed, then trace and traffic, then method. Invalid runs: a run is invalid if
matrix_e5.sh moves it to _failed (no summary, or a gap in the controller log such as a suspend),
or if it overlapped an install. It is rerun once with the same seed and listed in
results/testbed_prereg_final/reruns.md. A run invalid twice is reported as missing; its pairs are
left out and counted.

## 6. Measures

Per run, from testbed/summarize_run.py:

- **Benign harm** (benign_harmed_pct): our measure, used by none of the compared papers: the share
  of benign flows refused at least once, never installed, dropped by a rule or whose first packet
  was lost. Reported with its four parts.
- **Attack occupancy**: attack share of the table after onset, mean over the three switches
  (attack_share_avg_pct_s11-s13); also each switch, and the maximum (the papers' Pa).
- **Service**: probe success (probe_post_success_pct) and lost first packets
  (benign_packet_in_lost_pct). Primary measures, tested in H3.
- **Detector false alarms in deployment**: benign entries evicted by the detector per minute,
  from the controller's flow log and the ground truth (added to summarize_run.py before the
  campaign), beside the offline rate (FEVER's detector: 0.72 % on T1B test rows).
- Hosts blocked (attack, benign), first attacker block (s), decision time, controller CPU and
  memory, Packet-In, Table-Full.

## 7. Confirmatory hypotheses

Pairs: same trace, attack and seed. Each test is a one-sided exact sign test with ties counted
against FEVER. **Holm over all the tests below together** (33 tests), alpha 0.05.

A pooled hypothesis is supported only if its test passes **and** no single attack contradicts it:
FEVER's mean over that attack's seeds is not worse than the comparator's by more than 0.1 point
of harm, 2 points of occupancy or 5 points of probe success. This keeps a large win on one attack
from hiding a loss on another.

T1B attack pairs for H1-H3: A2, A5, A7 (3 seeds each) and A4, E9P (5 each) = 19 pairs per
comparator.

- **H1 (harm)** FEVER harms fewer benign flows than each of FTMaster, FTOP, FTODefender, FloRa,
  DMS-BTT and rDefender. 6 tests.
- **H2 (occupancy)** FEVER's attack occupancy is lower than each of the six. 6 tests.
- **H3 (service, non-inferiority)** FEVER's probe success is above each of the six's minus 5
  points (a pair counts for FEVER if FEVER's probe success > the comparator's - 5). 6 tests.
- **H4 (equal data)** On A4 and E9P (10 pairs), FEVER's attack occupancy is lower than each
  pooled baseline's. 5 tests. If H4 fails, the preregistered reading is the weaker claim: FEVER
  matches pooled training without sharing raw rows, which holds if FEVER's mean occupancy is within
  2 points of each pooled baseline's on A4 and on E9P (reported, not tested).
- **H5 (held out)** On A6 and EVX on T1B (10 pairs), FEVER's attack occupancy is lower than each
  of the six. 6 tests. On UHt (A2, A4, E9P, 9 pairs), lower than FTMaster's, DMS-BTT's and
  rDefender's. 3 tests.
- **H6 (federation)** On A4 and E9P (10 pairs), FEVER's attack occupancy is lower than FEVER
  without sharing's. 1 test.
- **H7 (no attack)** Bars, not tests: in FEVER's benign-only runs on T1B and on UHt, mean harm
  <= 0.1 % and mean lost first packets <= 1 %; FEVER blocks no benign host in any run.

Stated now, from the development runs: on A2, Spoof and Pulse several methods reach harm near
0.00 %, so ties may cost H1; under Aware FEVER's probe success was about 13 %, so H3 may fail
there; EVX is designed to defeat the volume rule, so H5 may fail on it. Each outcome is reported
as it is.

## 8. Reported regardless (not tests)

- **Per attack** (each trace): for every method and measure the mean and min/max over seeds, and
  FEVER's paired difference to each comparator with its min/max and wins (as in
  results/testbed_prereg_v5/exploratory_close.md), so that no result rests only on a pooled test.
- Ablations against FEVER per attack, with paired wins (docs/fever_ablation_plan.md), and FEVER
  without the detector against rDefender.
- Bootstrap 95 % intervals (over seeds) of FEVER's difference to DMS-BTT and FTMaster per attack.
- The 600 s check (section 5): FEVER, DMS-BTT and FTMaster on A4 and E9P at seed 4160 (6 runs,
  not tested), since most compared papers run 600 s.

## 9. Scope of the claims

- **Federated training, deployed in one controller.** FEVER's detector is trained across three
  controllers' recordings; on the testbed it runs in one controller (C3's network, and UHt's). The
  training ran as three worker processes on one machine. Live federation over a network (Flower
  server and controller processes) is separate work and not claimed here.
- **Privacy.** Raw rows are not shared. Lossless federated XGBoost shares per-round gradient and
  hessian histogram sums (about 8.7 MB per tree, 2.6 GB for 300 trees), which are known to leak
  information about the training data; no secure aggregation or differential privacy is used. The
  paper states this as a limitation and claims no privacy beyond "raw rows are not shared".
- **Scale.** Three switches, four benign hosts, two attackers, one laptop, 300 s runs; stated as
  limitations, with the 600 s check above.
- **Permanent blocks.** A blocked host stays blocked until an operator lifts it; benign hosts
  blocked are reported for every run, and the cost of a false block is discussed.
- **Controller cost.** Scoring a full table takes 0.23 s against 0.09 s for v6; decision time and
  CPU are reported for every method.

## 10. Before the first run

1. Retrain and export the baselines on C3's rows and on pooled rows (section 4) and the ablation
   detector (fever-ll-local); code fever-ll-novol, fever-noml and the EVX attack; add the benign
   eviction count to summarize_run.py; calibrate UHt thresholds on tbt_UHt_benign_none_s4190.
   Output in results/testbed_baselines_tb/.
2. Fidelity report (section 4).
3. User reinstalls the testbed.
4. Smoke runs on seed 4183.
5. testbed/analyze_final.py written and committed; this document fixed: SHA-256 of this file and
   of the analysis script in results/testbed_prereg_final/preregistration.json, committed before
   run 1.
