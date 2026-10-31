# Run plan: the related papers' experiments on our setup

Source: `Other Paper/experiments_summary.md` (12 papers). This plan maps every experiment
those papers run to our simulator (loftbench) and Mininet/Ryu testbed, says what already
exists, and lists the runs still needed with counts and time. It refines P0-A, P0-D, P1-C and
P1-E of `docs/conference_revision_plan.md`.

Timing basis on this 4-core laptop: a simulator episode of 300 s takes about 0.65 s with 4
workers (revision 1: 1,680 episodes in 1,100 s), a 600 s episode about 1.3 s; a testbed run of
600 s takes about 10.5 min, one at a time.

## Rules

- Baselines are tuned on validation seeds 2000-2002 only, like our method.
- One-shot test seeds: **11000-11009** (simulator) and **4100-4102** (testbed). Never used before.
  Used so far: 4000, 5000, 6000, 7000, 8000-8003, 9000, 10000 ranges.
- Every deviation from a paper's mechanism is written down, as was done for DMS-BTT.
- A baseline goes on the testbed only after it reproduces its own paper's direction in the
  simulator (gate G1).

## 1. What the papers measure, and where we stand

| Metric (papers) | Simulator today | Testbed today | To add |
|---|---|---|---|
| Acc / P / R / F1 / FPR / FNR / MCC (3-9, 11, 12) | P/R/F1 (scale, ml_compare) | — | FPR, FNR, MCC, per-variant and mixed |
| Avg / max attack share Pa (3, 4, 6, 7, 11, 12) | `avg_attack_occ`, `max_attack_occ` | from summary | — |
| Avg table usage (4, 6, 7, 9, 11, 12) | `avg_benign_occ` + attack share | partly | one column |
| Earliest overflow, overflow count, total overflow time (4, 6, 7, 9, 11, 12) | `first_overflow_s`, `overflow_seconds` | `table_full` | overflow count (episodes) |
| Packet-In, Table-Full (3, 4, 6, 7, 11, 12) | `packet_in`, `table_full` | yes | — |
| Packet-In loss rate (10) | — | `benign_packet_in_lost_pct` | simulator column |
| New-flow RTT and throughput (1, 8) | — | — | ping + iperf in the traffic driver |
| Per-module time (3, 4, 5, 7, 10, 11) | `decision_ms_mean`, `p99` | — | controller timing log |
| CPU / memory (most) | — | CPU | RSS (needs reinstall) |
| Time series of rules, Pa, Packet-In (all) | `record_ts` | per-poll log | figure |
| **Benign flows harmed (ours, none of theirs)** | yes | yes | — |

## 2. Experiments

### E1. Offline classification table (P1-C) — simulator, about 2 h, no new code beyond metrics

What the papers do: offline Acc/P/R/F1/FPR/FNR(/MCC) on a held-out split, several classifiers
(SFTO-Guard 8, FTMaster 6, FTOP 6, FloRa 5, DMS-BTT 7), table-state detector and per-rule
classifier reported separately.

Runs:
- Classifiers: MLP (ours, federated), RF, CatBoost, HGB (stand-in for LightGBM), XGBoost, KNN,
  linear SVM, LR. Local, pooled and federated (MLP by weight averaging; the rest by averaging
  the local models' outputs).
- Data: the existing train/val/test_off splits of D1-D3 and T1; per variant A1-A7 and mixed;
  A6 held out (no paper tests on unseen attacks).
- Also the table-state task (attack vs no attack per poll) that the two-stage papers use, so
  our numbers sit beside theirs.
- 3 training seeds. Metrics: everything in the first row of the table above, plus per-rule
  inference time.
- Needs: `pip install xgboost lightgbm` in `~/.venvs/loft` (both missing now).

### E2. Baselines in the simulator (P0-A) — about 3 days of coding, about 1 h of runs

| Baseline | Paper | Mechanism to implement | Have |
|---|---|---|---|
| REFUSE | all | no defense | yes (`none`) |
| EVICT | 4, 6, 7, 12 | OVS eviction when full | yes (`OVSEvict`) |
| SIFT | 4, 6, 7, 9, 10, 12 | sampling-based eviction of low-rate entries | no |
| TableGuard | 6, 7, 10, 11, 12 | table-usage-triggered eviction of small long-lived rules | no |
| FTMaster | 4, 8, 9, 11 | XGBoost table-state + XGBoost per rule (DT, NP, NB, MPS, MPIT, MTS); evict then block source | no |
| SFTO-Guard | 3, 6, 7, 9, 11 | rule-count predictor + LightGBM detector; adaptive eviction proportion Pe | no |
| FTOP | 7, 12 | Kalman predictor + RF detector + RF per rule + significance-based preventer | no |
| FloRa | 9 | CatBoost with PAF / CRS / PSI; evict, protect elephants, block source | no |
| rDefender | 10 | per-port ATOS detection, random deletion inside attacked ports, deletion-count rule | no |
| DMS-BTT | 12 | two thresholds, CatBoost state + per rule | yes (+ blocklist) |

Gate G1 checks, simulator, validation seeds, D1-D3 and T1, A1-A3:
- FTMaster: attack share below 25 % (their Table VI: 17.6 %).
- SFTO-Guard: attack share below 10 % and the rule count held near its threshold.
- FTOP / DMS-BTT: Pa about 20 % / 5 %.
- rDefender: malicious rules fall under LA and HA; Packet-In loss 0.
- SIFT, TableGuard: worse than the ML defenses, better than REFUSE (FTODefender, FTOP order).

Runs: 7 new baselines × 4 traces × 4 (3 attacks + benign) × 3 val seeds = 336 episodes for
the gate, plus a small knob search per baseline (≤ 5 settings), about 1,700 episodes, about
40 min.

### E3. Main comparison in DMS-BTT Table 6 format (P0-D, simulator half) — about 1.5 h

The table every Tang et al. paper prints, on our full attack set.

- Protocol: 600 s, attack from 50 s, table 3,500, idle timeout 10 s (DMS-BTT's).
- Traces: D1, D2, D3 and T1 (bigFlows).
- Attacks: A1-A3 (the papers' own groups), A4 mimicry, A5 spoof, A6 unseen slow fill,
  A7 pulse, X1 fast refresh; plus benign only.
- Defenses (13): REFUSE, EVICT, SIFT, TableGuard, FTMaster, SFTO-Guard, FTOP, FloRa,
  rDefender, DMS-BTT, v2.1 (local), FL-DualGuard v2.1, v2.1 + PortGuard.
- Seeds 11000-11009, one shot.
- 13 × 4 × 9 × 10 = 4,680 episodes, about 1.7 h.
- Reported: avg Pa, max Pa, avg table usage, earliest overflow, overflow count, total overflow
  time, Packet-In, Table-Full (their columns), then benign harmed, Packet-In loss, decision
  time (ours). Paired cluster tests against FL-DualGuard, Holm-corrected.
- Figure: rule count, Pa and Packet-In over time for seed 11000, T1 A2.

### E4. Same comparison on the testbed (P0-D, testbed half) — about 26 testbed hours

- Port the E2 baselines to `testbed/loft_ryu_app.py` through `build_defense`; 2-run smoke
  test each.
- Controller logging, one reinstall by you: per-label occupancy (avg/max Pa), RSS memory,
  per-module time.
- T1, 600 s, attack from 50 s; attacks A1-A3, A4, X1; 10 defenses (REFUSE, EVICT, SIFT,
  TableGuard, FTMaster, rDefender, DMS-BTT, v2.1, PortGuard, FL-DualGuard); seeds 4100-4102.
- 5 × 10 × 3 = 150 runs, about 26 h over 2-3 nights.

### E5. Service-level harm (LOFT, ALFO-Guard) — testbed, about 3 h

- During E4-style runs, a probe host opens 50 new flows (ping RTT, 100 rounds; iperf 1 MB),
  as LOFT and ALFO-Guard do. Compare REFUSE, DMS-BTT, FTMaster, rDefender, FL-DualGuard on
  T1 A2 and A4 × 3 seeds = 30 runs, about 5 h; or fold it into E4 at no extra runs if the
  probe does not disturb the table (check on 2 runs first).

### E6. Table size and idle timeout sweeps (FTMaster, FloRa, FTShield, rDefender) — simulator, about 1 h

- Table 1,500 / 2,000 / 3,000 / 3,500 / 4,000 with τ recalibrated per size on validation seeds.
- Idle timeout 10 / 20 / 30 s (FloRa uses 20, rDefender 30).
- Defenses: REFUSE, FTMaster, DMS-BTT, rDefender, FL-DualGuard. Traces D1-D3 and T1;
  A1-A3; 5 seeds (11000-11004).
- (5 sizes + 2 extra timeouts) × 5 × 4 × 3 × 5 = 2,100 episodes, about 45 min.
- Testbed spot check: 2K and 4K × {DMS-BTT, FL-DualGuard} on T1 A2 × 1 seed = 4 runs, 45 min.

### E7. Threshold sensitivity (FTMaster 70/80/90 %, FTShield 60/70/80 %, DMS-BTT Pe, FTODefender TH2) — simulator, about 20 min

- Our counterparts: occupancy trigger ρ 0.5 / 0.6 / 0.7 / 0.8 / 0.9 and the flag budget
  0.5 / 1 / 2 / 5 %. Reported as sensitivity only, on validation seeds (the selected values
  stay fixed). 4 traces × 8 attacks × 3 seeds × 9 settings = 864 episodes.

### E8. Flash crowds (FTOP) — simulator, about 10 min

- Benign-only traffic with the flash-crowd generator turned up (FTOP doubles the rate) and no
  attack; plus flash crowd during A2. All 13 defenses × 4 traces × 2 × 10 seeds = 1,040
  episodes. Question: which defenses evict benign flows when the overflow is benign?

### E9. Stronger and adaptive attackers (rDefender, ALFO) — about 1 day coding, 30 min runs

- rDefender's four attacks: LA (300 pps), HA (2,000 pps), ALA (benign-trace replay, close to
  our A4), AHA.
- ALFO: the attacker adapts to the eviction policy (FIFO batches, random flow count, LRU
  cycle); run it against EVICT with each policy and against the ML defenses.
- 4 new attack variants × 13 defenses × 4 traces × 5 seeds = 1,040 episodes.

### E10. Overhead (most papers) — testbed, from E4 logs

- CPU and RSS of the controller with and without each defense; per-module decision time;
  FL communication bytes per round (already in `train_info.json`).

### Not planned

- Hardware or P4 (LOFT, rDefender, FTShield, FloRa): no hardware here; stated as a limit.
- GASF-IPP: different threat model (TCP-targeted LDoS); cited, not compared.
- Rule-count prediction RMSE (SFTO-Guard): only if SFTO-Guard's predictor is built in E2.

## 3. Order and time

| Step | Work | Compute | Your part |
|---|---|---|---|
| 1 | E1 offline table | 2 h | approve `pip install xgboost lightgbm` |
| 2 | E2 baselines + gate G1 | 3 days coding, 40 min runs | — |
| 3 | E3 main simulator comparison | 1.7 h | — |
| 4 | E6, E7, E8 sweeps | 1.3 h | — |
| 5 | E9 adaptive attackers | 1 day coding, 30 min | — |
| 6 | Port baselines to Ryu, add logging | 1.5 days | run `sudo bash testbed/root/install.sh` |
| 7 | E4 + E5 testbed | 26-31 h over 2-3 nights | keep the laptop on |

About 6-7 working days plus 2-3 testbed nights. Steps 1, 3 and 4 run unattended once the
baselines exist; the testbed never runs at the same time as simulator jobs.
