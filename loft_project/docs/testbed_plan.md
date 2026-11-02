# Definitive experiment plan (from 2026-11-03)

Goal: a top-tier submission whose evaluation answers every weakness found so far. New results
are the related papers' own experiments on the Mininet / Open vSwitch / Ryu testbed. Simulator
runs only where a testbed run needs a selection step, plus quarantine round 2 (kept by the user).

## 1. Weaknesses and how each is closed

| # | Weakness | Closed by | Done when |
|---|---|---|---|
| W1 | v2.1 alone loses to mimicry on bigFlows (A4 36.7 %, A6 38.7 %; FTOP 8.2 % overall) | Claim one final system (DualGuard + PortGuard, section 2), v2.1 alone as ablation | T1 shows the final system below every baseline on A4 |
| W2 | Controller overload on the testbed (36 % new connections under A2; 19-40 % lost first packets under the adaptive attack) | Flow hold as a T1 ablation; quarantine round 2; lost first packets reported next to harm for every defense | T1 table has harm, lost first packets and probe success side by side |
| W3 | PortGuard assumes one host per port (shared ports: 17-24 %) | Host identity: PortGuard's quota keyed on source MAC instead of ingress port (no retuning) | T1 on the tree, whose core ports are shared, with port vs MAC identity |
| W4 | FedAvg false demotes at 6-9 controllers (IoT 8.5-11 % vs pooled 2.6-2.9 %) | Personalized ensemble (federated + local MLP, scores averaged), simulator K = 3, 6, 9 | Gate G4 decides: extension reported, or stated limitation. T1 keeps today's model either way |
| W5 | Flash crowds: PortGuard 7.3 %; fair eviction fixes harm but overloads the controller | Quarantine round 2 (simulator, then testbed); T3 flash crowds | Gate G2 decides whether fair eviction joins the final system |
| W6 | Patchwork of add-ons; FloodGuard did not help floods | Freeze one final system before T1 (gate G3); the rest are ablations; FloodGuard dropped from the claim | Frozen in `results/final_system.json` before T1 starts |
| W7 | No hardware switch | Stated limitation; full testbed campaign instead (most Tang et al. papers are Mininet-only too) | Limitation paragraph |
| W8 | Missing baselines SIFT and TableGuard (compared in 6 and 5 of the 12 papers) | Implement from their papers, gate G1 in the simulator, port to the testbed | Both in T1 |
| W9 | Mostly synthetic traffic; univ1 not used | T1 on bigFlows; T5 on IMC-10 univ2, and univ1 if fetched | T5 done |
| W10 | No full classifier metrics table (Acc / P / R / F1 / FPR / MCC) | E1 offline table from existing datasets: MLP, RF, HGB, CatBoost; local / federated / pooled | `results/e1_offline/` |
| W11 | Memory not measured | Controller RSS logged in every run (pidstat -r) | T6 overhead table |
| W12 | One controller per run, one laptop; 3 testbed seeds | Stated; statistical tests come from the simulator's 10-seed results; testbed reports per-seed ranges and the share of seeds where the ordering holds | Limitation paragraph |

## 2. The system the paper claims

Fixed at gate G3 (day 1, before T1) and written to `results/final_system.json`:

- **FL-DualGuard** = federated MLP v2.1 (unchanged) + PortGuard (revision 4b knobs) with host
  (MAC) identity.
- **+ fair eviction with churn quarantine** only if gate G2 passes.
- Ablations in T1: v2.1 alone, v2.1 + PortGuard (port identity), v2.1 + PortGuard + flow hold.

## 3. Gates (decided by numbers fixed here, before the runs)

| Gate | Question | Pass rule | If it fails |
|---|---|---|---|
| G1 | Do our SIFT and TableGuard behave like their papers? | Simulator validation seeds: each harms less than no defense and more than DMS-BTT on A1-A3 (the order FTODefender and FTOP report) | Debug once against the paper; if still off, report with the deviation written down |
| G2 | Does quarantine round 2 make fair eviction usable on the testbed? | Simulator FQ1-FQ4 hold, and on the testbed (D1, 9 runs) under the adaptive attack fair eviction + quarantine has total benign impact <= PortGuard's (24.2 %) and flash-crowd harm <= 1 % | Final system without fair eviction; fair eviction reported as an ablation with its cost |
| G3 | Freeze the final system | Section 2 with G2's outcome; tree smoke test T0 passes (every switch logs, overflows under attack, the defense acts on each) | Fix the testbed before any long run |
| G4 | Does personalization fix FedAvg at 6-9 controllers? | At K = 9: IoT online harm drops >= 2 points and recall on attacks no controller saw drops <= 2 points | Stated limitation with the flow-level calibration result |

## 4. Schedule

Testbed runs: 300 s, attack at 50 s, one at a time, about 6.5 min each, nothing else running
on the laptop meanwhile. Simulator work fits before or between testbed blocks, never during.

| Day | Daytime (code, simulator, short runs) | Testbed block |
|---|---|---|
| 1 | Code: SIFT, TableGuard; PortGuard host identity; RSS logging. **You reinstall.** Simulator: G1 (40 min), quarantine round 2 (40 min), E1 offline table (1 h), G4 personalization (1 h). Testbed: T0 smoke (4 runs), quarantine round 2 testbed (9 runs, D1 dumbbell, against results/testbed_fe). Decide G2, G3. | T1 starts in the evening |
| 2 | Analyse T1's first half as it arrives (no heavy scripts while it runs) | T1 continues (about 23 h in all) |
| 3 | T1 report: main table, ablations, overhead (T6) | T2 (6.5 h) |
| 4 | Code: rDefender's LA / HA / ALA / AHA and ALFO's adaptive attack on the testbed driver; flash-crowd replay for traces | T4 (10 h) |
| 5 | T4 report | T3 (6 h) |
| 6 | Fetch univ1 if available; export trace models | T5 (9 h) |
| 7 | All reports, brief, paper tables and figures | - |

## 5. Experiments

All on the three-switch tree (core + two access switches, all tables 3,500 and monitored, one
controller), seeds 4100-4102, new-connection probe on, unless stated.

| ID | Papers | Traffic | Defenses | Runs | Reported |
|---|---|---|---|---|---|
| T0 | - | bigFlows; A2, benign | none, DualGuard | 4 | every switch logs, overflows, defense acts |
| T1 | all | bigFlows; A1, A2, A3, A4, adaptive E9P, benign | none, OVS eviction, SIFT, TableGuard, DMS-BTT, FTMaster, FTOP, rDefender, v2.1, v2.1 + PortGuard (port), v2.1 + PortGuard + hold, **final system** | 6 x 12 x 3 = 216 | the papers' table (avg / max attack share, table usage, earliest overflow, overflow time, Packet-In, Table-Full) per switch, plus benign harm, lost first packets, probe success, flow-mods, CPU, RSS |
| T2 | FTMaster, FloRa, rDefender | bigFlows; A2 | none, DMS-BTT, FTMaster, rDefender, final | table 2K / 4K, idle 20 / 30 s (3K / 10 s from T1): 4 x 5 x 3 = 60 | same columns per setting |
| T3 | FTOP | bigFlows replayed at 2x for 12 s windows; no attack, and with A2 | 9 of T1's defenses (no ablations) | 2 x 9 x 3 = 54 | benign harm under a benign overflow |
| T4 | rDefender, ALFO | LA, HA, ALA, AHA; ALFO against eviction | none, OVS eviction, rDefender, DMS-BTT, FTMaster, final | 5 x 6 x 3 = 90 | malicious-rule count, harm, Packet-In loss |
| T5 | FTOP (univ2), FTMaster / FloRa / rDefender (univ1) | univ2 (and univ1); A2, A4, benign | 9 of T1's defenses | 3 x 9 x 3 = 81 per trace | T1's columns |
| T6 | most | from T1's logs | all | 0 | CPU, RSS, decision time, flow-mods, FL bytes per round |
| Q2 | ours | simulator, then D1 dumbbell A2 / E9P / F4 | fair eviction + quarantine round 2 | 9 | gate G2 |
| E1 | 9 of 12 | offline datasets | MLP, RF, HGB, CatBoost x local / federated / pooled | 0 | Acc, P, R, F1, FPR, FNR, MCC |
| G4 | ours | simulator, K = 3, 6, 9 | FedAvg vs federated + local | 0 | IoT harm, unseen-attack recall |

About 514 testbed runs, about 56 testbed hours, over 6 nights and days.

## 6. What goes in the paper

- Table: T1 in the papers' format, final system against 10 configurations.
- Ablation table: v2.1 alone, + PortGuard (port vs host identity), + hold, + fair eviction.
- Figures: rule count, attack share and Packet-In over time for one T1 seed (A2, adaptive); harm
  vs table size and idle timeout (T2).
- Robustness: T3 flash crowds, T4 stronger and adaptive attackers, T5 second trace.
- Overhead: T6. Offline classifier table: E1.
- Limitations: no hardware; one controller per run on one host; 3 testbed seeds (statistics
  from the simulator); G4's outcome.

## 7. Topology (unchanged from the user's choice)

```
            srv (server)
             |
          s{k}1  core       table 3,500, monitored
          /     \\
     s{k}2       s{k}3      access switches, tables 3,500, monitored
    h1 h2 h5    h3 h4 h6    h5, h6 attackers (one per access switch)
```
