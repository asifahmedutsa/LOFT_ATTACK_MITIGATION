# Training on the testbed: real traffic recorded at the controller

*Fixed 8 November 2026, before any of the runs below. Supersedes the simulator rows of
docs/realfl_plan.md as FEVER's training data; those results stay as a supplementary comparison.*

## Why

Every LOFT defense we compare with trains the same way: a real capture is replayed through an
emulated SDN (Mininet, Open vSwitch, Ryu), the attack comes from a script, the features are
recorded at the controller and labelled from ground truth (SFTO-Guard and FTOP: IMC-10 univ at
1,200 / 1,000 pps; DMS-BTT: bigFlows at 300 pps per host; FTMaster and FloRa: IMC-10 univ1).
FEVER's rows so far came from our flow-table simulator replaying the same captures, and E11
(results/e11_testbed) showed that simulator rows and testbed rows differ (A2 recall 99.5 % in the
simulator, 95.1 % on testbed rows). From now on FEVER and the baselines are trained on rows
recorded on the testbed.

## Recording

- Testbed as in every campaign: Mininet tree (core s11, access s12, s13), Open vSwitch, one Ryu
  controller per network, capacity 3,500, idle timeout 10 s, 1 s polls, 4 benign hosts and 2
  attackers, 300 s runs, attack from 50 s, defense none (nothing alters the traffic), entry log on
  (`run_testbed --entry-log`): every entry's counters at every poll on all three switches.
- Rows: testbed/entrylog.py rebuilds the 17 features the controller computes (FeatureTracker) on
  the controller's own poll times, a random 5 % of entries per poll and switch, labelled from the
  hosts' ground-truth files; entries of unknown origin (ping, probe) are left out.

| Network | Capture | Replay rate on the testbed | Role |
|---|---|---|---|
| C1 | univ2 part 0 | 1,000 pps (FTOP's rate; domain U1t) | controller |
| C2 | univ2 part 3 | 1,000 pps (U2t) | controller |
| C3 | bigFlows T1A (first 40 %) | 600 pps (T1A at benign scale 0.5, the testbed's calibrated bigFlows load) | controller |
| T1B | bigFlows T1B (last 60 %) | 600 pps (T1B at benign scale 0.5, as every campaign) | test, C3's network |
| UH | univ2 part 6 | 1,000 pps (UHt) | held-out test (if time allows) |

univ2's 1,000 pps is checked first with the testbed's load gate G0 (benign only, no defense:
lost first packets <= 0.1 % and probe success 100 %) on U1t, U2t and UHt with seed 4190, then on
the one with the most lost first packets with seeds 4191-4192 (testbed/record_tbtrain.sh cal). If it
fails, univ2 is replayed at 500 pps; this is decided before any attack run.

- Attacks per controller as before: C1 G1 (A1) + Mimic (A4), C2 G2 (A2) + Spoof (A5),
  C3 G3 (A3) + Pulse (A7); Slow (A6) and Aware (E9P) seen by no one.
- Seeds (none used on the testbed before): training 4170-4172; threshold (benign only, C3's
  network T1A) 4173-4175; test 4176-4178.
- Runs: training 3 networks x (2 attacks + benign) x 3 seeds = 27; threshold 3; T1B test 8 attacks
  + benign x 3 seeds = 27; total 57 runs, about 6.5 h, one at a time. UH test (27 runs, 3 h) after
  that if the laptop is free.

## Training (unchanged methods, testbed rows)

On each controller's own rows: local only (C3), one-shot sharing (CatBoost), federated XGBoost
bagging (Flower), FedProx (Flower), lossless federated XGBoost (three workers, histogram sums),
pooled XGBoost and CatBoost (references). Settings as in docs/realfl_plan.md. Thresholds: 0.1 % of
the T1A benign rows of seeds 4173-4175 (for T1B); UH has no controller, so its threshold is 0.1 %
of its own test benign rows (an oracle setting, reported as such).

The baselines are retrained on the same recordings, each with its own paper's features and model,
as far as the entry logs carry them: FTMaster, FTOP, FloRa, DMS-BTT and FTODefender on C3's network
(T1A, seeds 4170-4172), as in their papers (one controller, one trace). Feature gaps are listed.

## Measures and choice

- Offline metrics as the other papers report them: accuracy, precision, recall, F1 and false-alarm
  rate on the T1B test rows (seeds 4176-4178), per attack and over all attacks.
- Exposure groups as before: seen locally, seen only by another controller, seen by no one.
- Score = mean of (recall seen only by another controller, recall seen by no one) on T1B.
- Choice: among the federated detectors with T1B benign false alarms <= 0.2 % (one-shot, bagging,
  FedProx, lossless), take the best score; FEVER's detector is the first of one-shot, bagging,
  FedProx, lossless (least shared first) whose score is within 1 point of that best.
- Confirmatory: H1 lossless score >= bagging score + 2 points on the testbed T1B test rows.

## Deployment check (testbed, development seeds)

The chosen detector runs in the controller (XGBoost through loftbench/treejson.py, parity < 1e-4).
FEVER with it against FEVER v6 on A2, A4, E9P and benign, seeds 4181-4182 (16 runs, about 2 h).
Passes if for A2, A4 and E9P harm <= v6 + 0.1 points and attack occupancy <= v6 + 2 points, no
benign host is blocked, and benign-only harm <= 0.1 %. If it fails, rule A is re-tuned on these
seeds over n_min {30, 50, 80} x frac_min {0.1, 0.2, 0.3} using recorded rows replayed in
the simulator, and checked again on seed 4183. The final campaign (4160-4162) is unchanged.

**Clarified 8 November, after the detector choice and before any deployment-check run.** On the
testbed, attack occupancy is the attack share of the table after onset, averaged over the three
switches (summarize_run.py attack_share_avg_pct_s11-s13); harm is benign_harmed_pct; the check
compares fever-fl with fever (v6 without PortGuard, as deployed) on T1B at 600 pps
(testbed/campaign_flcheck.sh, testbed/analyze_flcheck.py).

## Amendment 1 (8 November 2026, after the offline results above, before any deployment-check run)

Requirement from the supervisor: FEVER's deployed detector must be trained by round-based federated
learning, in which the controllers exchange model updates over several rounds. One-shot sharing (a
single exchange of finished local models) therefore no longer qualifies; it stays in the paper as a
comparison. This amendment is made after the offline T1B results were seen
(results/tbfl/report.md), and is reported as such.

- Offline reference added: FedAvg (Flower; FedProx's script with mu = 0, 30 rounds, same rows,
  seed and network as FedProx). It is not a candidate for deployment and does not enter the
  choice rule above; results/tbfl/choice.json is unchanged.
- Deployment check with three arms instead of two, all on T1B at 600 pps, A2, A4, E9P and benign,
  seeds 4181-4182 (24 runs, about 3 h): fever (v6 as deployed), fever-fl-bag (Flower XGBoost
  bagging, threshold 0.7376) and fever-fl-ll (lossless federated XGBoost, threshold 0.4953). Both
  thresholds are 0.1 % of the T1A benign rows of seeds 4173-4175, as offline; everything else
  (block rule, rho, volume rule) is v6's. The lossless model enters although its offline T1B false
  alarms (0.72 %) exceed the 0.2 % limit, because the check measures what those false alarms cost
  on the testbed (harm and benign hosts blocked); the offline limit is reported next to it.
- Pass conditions per arm unchanged (harm <= fever + 0.1 and attack occupancy <= fever + 2 on A2,
  A4 and E9P; no benign host blocked; benign-only harm <= 0.1 %).
- Deployed detector: if both arms pass, the one with the lower mean attack occupancy over A2, A4
  and E9P, unless the two are within 1 point, in which case bagging (it shares less). If one
  passes, that one. If neither passes, rule A is re-tuned for each as described above and checked
  on seed 4183, and the same order applies.

**Note, 8 November, 14:30 (fix before any valid deployment-check result).** The first four runs
(A2, fever and fever-fl-bag, seeds 4181-4182) were stopped and set aside
(~/loft-runs/_invalid_flc_nodroprules): the controller gave drop rules to hosts blocked by the
evict-block layer only when that layer sat inside PortGuard, so fever and fever-fl-* (the layer
alone) blocked hosts without drop rules (no host_block logged, 32 % lost first packets in every
arm). testbed/loft_ryu_app.py now gives the layer alone the same drop rules. The v6 campaign
(ensguard-v6, with PortGuard) is not affected. The check is rerun in full with unchanged
conditions.
