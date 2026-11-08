# Final testbed campaign: preregistration

*Draft, 8 November 2026. Not yet fixed: it is fixed (hashed, results/testbed_prereg_final/
preregistration.json) after the user's approval and before any run on seeds 4160-4162. No run on
these seeds exists (checked in ~/loft-runs, 8 November).*

## 1. The system under test

FEVER as frozen by the deployment check (docs/testbed_training_plan.md, amendment 1;
results/tbfl/flcheck.md):

- Detector: lossless federated XGBoost (three controllers, histogram sums, 300 trees), trained on
  the testbed recordings of C1-C3 (seeds 4170-4172); controller config
  results/v21/exported/ens_config_fl_ll.json, T1B threshold 0.4953 (0.1 % of the T1A benign rows
  of seeds 4173-4175).
- Response: v6's evict-block layer (rule A: n_min 50, frac_min 0.2, k 3; volume rule per switch;
  permanent blocks), host identity on the tree, drop rules for blocked hosts.
- No PortGuard (results/tbfl/flcheck_pg.md: with PortGuard the attackers are blocked later and more
  new connections fail).
- Controller defense name: fever-fl-ll. Nothing in it is changed after this document is fixed.

## 2. Testbed

As in every campaign since v5: Mininet tree (core s11, access s12, s13), Open vSwitch, one Ryu
controller, table capacity 3,500, idle timeout 10 s, 1 s polls, 4 benign hosts and 2 attackers,
bigFlows T1B at 600 pps (benign scale 0.5), 300 s runs, attack from 50 s, new-flow probe on
(testbed/matrix_e5.sh with E5_DOM=T1B E5_TOPO=tree3 E5_BSCALE=0.5). Mains power only.

## 3. Methods

| Name | Defense | Detector training |
|---|---|---|
| none | no defense | - |
| FTMaster | ftmaster | retrained on testbed rows (section 4) |
| FTOP | ftop | retrained on testbed rows |
| FTODefender | ftodefender | retrained on testbed rows |
| FloRa | flora | retrained on testbed rows |
| DMS-BTT | dms-btt (as published) | retrained on testbed rows |
| rDefender | rdefender | no learned model |
| FEVER | fever-fl-ll | section 1 |

Ablations (FEVER with one part removed, everything else unchanged):

| Name | Defense | Change |
|---|---|---|
| FEVER without sharing | fever-ll-local | XGBoost trained on C3's rows only, with the lossless model's settings (300 trees, same parameters); threshold by the same rule |
| FEVER without the volume rule | fever-ll-novol | volume rule off |
| FEVER without the detector | fever-noml | no detector: volume rule only |

## 4. Baselines retrained on the testbed (before the campaign)

Each baseline is trained as in its paper (one controller, one trace) on C3's network: T1A
recordings, seeds 4170-4172 (attacks A3, A7 and benign), with its own features and model as
implemented in loftbench, from the entry logs. Each threshold or knob that the paper sets on
validation data is set on the T1A benign recordings of seeds 4173-4175. Features the entry logs
do not carry are listed per baseline in results/testbed_baselines_tb/gaps.md.

Fidelity check, on the T1B test recordings (seeds 4176-4178), before the campaign: a retrained
baseline replaces its earlier simulator-trained model only if its recall on the standard attacks
(G1-G3, Spoof, Pulse) is at least that model's minus 5 points, at false alarms at most 1 %.
Otherwise the simulator-trained model is kept and the reason reported.

## 5. Runs

- Traffic: G2 (A2), Mimic (A4), Aware (E9P), Spoof (A5), Pulse (A7), benign only.
- Seeds: 4160, 4161, 4162 (never used on the testbed).
- Main: 8 methods x 6 traffic x 3 seeds = 144 runs. Ablations: 3 x (G2, Mimic, Aware) x 3 seeds =
  27 runs. Total 171 runs, about 15.5 h, one at a time, over two or three nights.
- Order: by seed, then traffic, then method, so that each seed's comparison is made in one stretch.
- Before the campaign, one smoke run per new or retrained defense on development seed 4183 (A2),
  which checks that it loads, blocks and logs; these runs are not results.

Invalid runs: a run is invalid if matrix_e5.sh moves it to _failed (no summary, or a gap in the
controller log such as a suspend), or if it overlapped an install. An invalid run is rerun once
with the same seed and recorded in results/testbed_prereg_final/reruns.md. A run that fails twice
is reported as missing; its pairs are left out of the tests and counted.

## 6. Measures

Per run, from testbed/summarize_run.py:

- Benign harm: benign_harmed_pct.
- Attack occupancy: attack share of the table after onset, mean over the three switches
  (attack_share_avg_pct_s11-s13).
- Lost first packets (benign_packet_in_lost_pct) and probe success (probe_post_success_pct).
- Hosts blocked (attack, benign), first attacker block (s), decision time, controller CPU and
  memory, and the papers' own columns (maximum attack share, Packet-In, Table-Full).

## 7. Confirmatory hypotheses

One-sided exact sign test over the 15 paired attack runs (5 attacks x 3 seeds, paired by attack
and seed), ties count against FEVER, Holm over the comparators of each hypothesis, alpha 0.05.

- **H1 (harm)** FEVER harms fewer benign flows than each of FTMaster, FTOP, FTODefender, FloRa,
  DMS-BTT and rDefender.
- **H2 (occupancy)** FEVER's attack occupancy is lower than each of the same six.
- **H3 (no attack)** In FEVER's three benign-only runs: mean harm <= 0.1 %, mean lost first
  packets <= 1 %; and FEVER blocks no benign host in any of its 18 runs.
- **H4 (federation)** On Mimic and Aware (6 pairs), FEVER's attack occupancy is lower than FEVER
  without sharing's (sign test over the 6 pairs, no Holm).

Expected from the development runs, stated now: on G2, Spoof and Pulse several defenses reach
harm near 0.00 %, so ties may cost H1; that outcome is reported as it is.

## 8. Reported regardless (not tests)

- Per attack and method: means and min/max over seeds of every measure in section 6.
- Ablations: FEVER against each ablation per attack, with paired wins, as in
  docs/fever_ablation_plan.md.
- Lost first packets and probe success beside harm for every method, since the pass rules of the
  deployment check did not include them.
- Aware is FEVER's weakest case in the development runs (probe success about 13 %); it is reported
  per method.

## 9. Before the first run

1. Retrain and export the baselines (section 4) and the ablation detector (fever-ll-local); code
   fever-ll-novol and fever-noml; results/testbed_baselines_tb/.
2. User reinstalls the testbed.
3. Smoke runs on seed 4183.
4. This document is fixed: SHA-256 written to results/testbed_prereg_final/preregistration.json
   and committed before run 1; the analysis script (testbed/analyze_final.py) is committed with
   it.
