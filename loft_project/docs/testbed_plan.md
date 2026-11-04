# Definitive experiment plan (from 2026-11-03, revised after a reviewer audit)

Goal: a top-tier submission whose evaluation answers every weakness found so far. New results
are the related papers' own experiments on the Mininet / Open vSwitch / Ryu testbed. Simulator
runs only where a testbed run needs a selection step, plus quarantine round 2 (kept by the user).

## 0. Reviewer audit of the first version of this plan (and what changed)

| # | A hostile reviewer would say | Severity | Change |
|---|---|---|---|
| R1 | "Testbed seeds 4100-4102 were used to design and calibrate (E5, fair eviction, quarantine round 2's trigger). Results on them are not held out." | critical | All T experiments and G2 use fresh seeds 4110-4114; 4100-4102 are design data only |
| R2 | "3 seeds cannot support any claim: the smallest possible p of a paired test is 0.25." | critical | 5 seeds in T1's key cells (A2, A4, adaptive, benign): if all 5 agree, one-sided sign test p = 0.031; Holm across hypotheses; bootstrap CIs |
| R3 | "You picked the final system after seeing results on the same attacks and trace you then evaluate on." | critical | Testbed hypotheses H1-H6 preregistered and hashed before T1; held-out evaluation named explicitly: T4's attacks and T5's traces were never used in design |
| R4 | "Is it the federated model or PortGuard that works? FL is in your title." | critical | T1 adds PortGuard alone (no DualGuard) and the final system with local (non-federated) models; held-out-attack cell shows what federation adds |
| R5 | "Your baselines are your own reimplementations; show they match their papers." | major | Fidelity table R0: each baseline's headline number under its paper's setting vs the published number, from existing gate results plus T1 |
| R6 | "Eviction defenses are measured with an inferred count (80-90 % recall), others exactly: biased in favour of eviction." | major | Day 1 check whether OVS 3.3 reports eviction to an OpenFlow 1.4 controller; if yes, eviction runs use OpenFlow 1.4 exact counts; if not, eviction harm is reported with the measured recall as an upper correction |
| R7 | "MAC identity is trivially spoofed." | major | T4 adds a MAC-rotating attacker; host identity is (access port, MAC) with the access switch enforcing port security (MACs pinned to their first port) |
| R8 | "An attacker who knows the quarantine trigger stays just under it." | major | If fair eviction + quarantine joins the final system, T4 adds a threshold-aware attacker (returns kept at 0.8 x r_min) |
| R9 | "Your testbed is saturated; losses are an emulation artefact." | major | Gate G0: on the tree, benign-only runs must lose <= 1 % of first packets (the old dumbbell loses 0.09-0.78 %). Losses under attack are then attack-induced control-plane load, reported for every defense |
| R10 | "A federated defense with no poisoning analysis?" | major | Simulator study P1 (needs your OK under the testbed-only rule): one poisoned controller, FedAvg vs coordinate median / trimmed mean, harm and recall |
| R11 | "Day 1 does five things; the schedule has no slack." | minor | 10-day schedule, 20 % rerun slack; priority tiers so cuts are predetermined |
| R12 | "Running each switch's own defense instance is your adaptation of single-switch baselines." | minor | Stated as a deviation for every baseline; FTMaster's Napnet also runs per-switch instances |

## 0a. Gate outcomes (2026-11-03)

- G1 passed (results/gate_g1): SIFT 16.3 %, TableGuard 16.8 % benign harm, between none 50.7 %
  and DMS-BTT 4.4 %; attack shares 45 % vs DMS-BTT's paper 38 % / 36 %.
- G2 failed in the simulator (results/fairevictq2): no round-2 setting kept flash-crowd harm within
  fair eviction's + 0.25 points (1.27-3.60 % vs 0.91 %), so no test; the Q2 testbed block is
  dropped and fair eviction is not in the final system.
- G3: final system frozen in results/final_system.json: dualguard+portguard+hostid.

## 0b. Adopted schedule: the 3-day core (2026-11-03)

The user chose the 3-day core. It keeps every critical fix (R1-R4) and cuts the rest:

| Block | Runs |
|---|---|
| T0 + G0: bigFlows; none and DualGuard x A2 and benign; OVS eviction x A2 (checks the exact eviction monitor) | 5 |
| Q2: D1 dumbbell; PortGuard, fair eviction, + quarantine x A2, adaptive, 4x crowd; seeds 4110-4112 | 27 |
| T1: bigFlows; A2, A4, adaptive, benign; seeds 4110-4114; 9 main configs (none, OVS eviction, SIFT, TableGuard, DMS-BTT, FTMaster, FTOP, rDefender, final) | 180 |
| T1 ablations: PortGuard alone (host identity), v2.1 + PortGuard (port identity); same cells | 40 |
| T1-fed (H5): D1 (where local models exist); A2 (seen only by another controller) and A6 (seen by none); final with federated vs local models; 5 seeds | 20 |
| T4: LA, HA, ALA, MAC-rotating; none, OVS eviction, rDefender, DMS-BTT, final; 3 seeds | 60 |
| T2: table 2K / 4K; A2; none, DMS-BTT, FTMaster, final; 3 seeds | 24 |
| T5: univ2; A2, A4; none, DMS-BTT, FTMaster, rDefender, final; 3 seeds | 30 |

386 runs, about 42 h. Dropped for later: A1, A3, T3, idle timeouts, univ1, ALFO, AHA, the
threshold-aware attacker (only needed if fair eviction joins the final system), G4 and P1 unless
time remains on day 3. H5 is tested on T1-fed instead of on bigFlows.

## 1. Weaknesses and how each is closed

| # | Weakness | Closed by | Done when |
|---|---|---|---|
| W1 | v2.1 alone loses to mimicry on bigFlows (A4 36.7 %, A6 38.7 %; FTOP 8.2 % overall) | One final system (section 2); v2.1 alone as ablation | H1 holds on A4 |
| W2 | Controller overload (36 % new connections under A2; 19-40 % lost first packets under the adaptive attack) | Flow hold ablation; quarantine round 2; lost first packets and probe success beside harm for every defense; G0 | T1 table |
| W3 | PortGuard assumes one host per port (shared ports: 17-24 %) | Host identity (access port, MAC) with port security; the tree's core ports are shared | H4 holds |
| W4 | FedAvg false demotes at 6-9 controllers | Personalized ensemble (federated + local), simulator K = 3, 6, 9 | Gate G4 |
| W5 | Flash crowds: PortGuard 7.3 %; fair eviction overloads the controller | Quarantine round 2; T3 | Gate G2, H5 |
| W6 | Patchwork of add-ons | One frozen final system; the rest are ablations; FloodGuard dropped | `results/final_system.json` before T1 |
| W7 | No hardware switch | Limitation; full testbed campaign | Limitations |
| W8 | SIFT and TableGuard missing | Implement, gate G1, port to the testbed | In T1 |
| W9 | Mostly synthetic traffic; no univ1 | T5 on univ2 (and univ1 if fetched) | T5 |
| W10 | No classifier metrics table | E1 offline: MLP, RF, HGB, CatBoost x local / federated / pooled | `results/e1_offline/` |
| W11 | Memory not measured | Controller RSS in every run | T6 |
| W12 | One controller per run, one laptop | Stated; G0 shows the emulation is not saturated without attack | Limitations |
| W13 | Seeds reused in design; 3 testbed seeds | R1, R2 | Fresh seeds, 5 in key cells |
| W14 | Federated poisoning not analysed | P1 (simulator, needs your OK) | Result or stated limitation |

## 2. The system the paper claims

Frozen at gate G3 (day 2, before T1) in `results/final_system.json`:

- **FL-DualGuard** = federated MLP v2.1 (unchanged) + PortGuard (revision 4b knobs) with host
  identity (access port, MAC).
- **+ fair eviction with churn quarantine** only if G2 passes.
- T1 ablations: v2.1 alone; PortGuard alone; v2.1 + PortGuard with port identity; + flow hold;
  final system with local models instead of federated.

## 3. Gates (rules fixed now, before the runs)

| Gate | Question | Pass rule | If it fails |
|---|---|---|---|
| G0 | Is the tree testbed unsaturated without attack? | Benign-only, no defense and DualGuard: lost first packets <= 1 %, probe success >= 98 % | Lower the trace replay rate until it passes, then keep that rate for every run |
| G1 | Do our SIFT and TableGuard behave like their papers? | Simulator validation seeds, A1-A3: each harms less than no defense and more than DMS-BTT | Debug once against the paper; else report with the deviation |
| G2 | Does quarantine round 2 make fair eviction usable? | Simulator FQ1-FQ4 hold; testbed (D1 dumbbell, fresh seeds 4110-4112, PortGuard / fair eviction / + quarantine rerun on them): under the adaptive attack, + quarantine's total benign impact <= PortGuard's, and its flash-crowd harm <= 1 % | Final system without fair eviction; it stays an ablation with its cost |
| G3 | Freeze the final system | Section 2 with G2's outcome; T0 passes (every switch logs, overflows under attack, each switch's defense acts) | Fix the testbed before any long run |
| G4 | Does personalization fix FedAvg at 6-9 controllers? | At K = 9: IoT online harm drops >= 2 points, recall on attacks no controller saw drops <= 2 points | Stated limitation |

## 4. Preregistered testbed hypotheses (hashed before T1; one-sided sign test over seeds, Holm)

- **H1** On every attack of T1 the final system harms fewer benign flows than each published
  baseline (SIFT, TableGuard, DMS-BTT, FTMaster, FTOP, rDefender).
- **H2** Under the adaptive attack its worst-case harm is below every baseline's.
- **H3** Without attack it harms <= 0.5 % of benign flows and loses <= 1 % of first packets.
- **H4** On the tree's core, host identity harms fewer benign flows than port identity under
  A2, A4 and the adaptive attack.
- **H5** Federation: on an attack the controller's local training never saw, the final system
  with federated models harms fewer benign flows than with local models.
- **H6** Held out: on T4's attacks and T5's trace, which were never used in design, H1 still
  holds against DMS-BTT, FTMaster and rDefender.

Reported regardless: the papers' columns, lost first packets, probe success, CPU and RSS.

## 5. Experiments (tree topology, fresh seeds, probe on)

| ID | Tier | Papers | Traffic | Defenses | Runs |
|---|---|---|---|---|---|
| T0 | must | - | bigFlows; A2, benign | none, DualGuard | 4 (+ G0 reruns if needed) |
| Q2 | must | ours | D1 dumbbell; A2, adaptive, 4x crowd | PortGuard, fair eviction, + quarantine, seeds 4110-4112 | 27 |
| T1 | must | all | bigFlows; A2, A4, adaptive, benign at 5 seeds (4110-4114); A1, A3 at 3 seeds | 9 main configs (none, OVS eviction, SIFT, TableGuard, DMS-BTT, FTMaster, FTOP, rDefender, final) on all; 5 ablations on the 5-seed cells | 9 x (4 x 5 + 2 x 3) + 5 x 4 x 5 = 334 |
| T4 | must | rDefender, ALFO; R7, R8 | LA, HA, ALA, AHA, ALFO vs eviction, MAC-rotating, (threshold-aware) | none, OVS eviction, rDefender, DMS-BTT, FTMaster, final | 7 x 6 x 3 = 126 |
| T2 | should | FTMaster, FloRa, rDefender | bigFlows A2; table 2K / 4K, idle 20 / 30 s | none, DMS-BTT, FTMaster, rDefender, final | 60 |
| T5 | should | FTOP; FTMaster, FloRa, rDefender | univ2 (and univ1); A2, A4, benign | the 9 main configs | 81 per trace |
| T3 | could | FTOP | bigFlows at 2x for 12 s windows; no attack, with A2 | the 9 main configs | 54 |
| T6 | must | most | T1 logs | all | 0 |
| E1 | must | 9 of 12 | offline | MLP, RF, HGB, CatBoost x local / federated / pooled | 0 |
| R0 | must | all | existing gate results + T1 | each baseline vs its paper's number | 0 |
| G4 | should | ours | simulator K = 3, 6, 9 | FedAvg vs federated + local | 0 |
| P1 | needs OK | FL security | simulator | FedAvg vs median / trimmed mean, 1 poisoned controller | 0 |

About 686 testbed runs, about 74 h; with 20 % rerun slack about 90 h. If time runs short, cut
from the bottom: T3, then univ1, then T2's idle settings.

## 6. Schedule (about 10 days)

| Day | Daytime | Testbed block (one at a time, nothing else running) |
|---|---|---|
| 1 | Code: SIFT, TableGuard, host identity + port security, RSS logging, OpenFlow 1.4 eviction check. **You reinstall.** Simulator: G1, quarantine round 2 selection and test | T0 + G0 (about 1 h), then Q2 (27 runs, 3 h) |
| 2 | Simulator: E1, G4 (P1 if approved). Decide G2, G3; write and hash H1-H6 | T1 starts |
| 3 | Watch T1 (no heavy scripts) | T1 continues (36 h in all) |
| 4 | T1 report, R0 fidelity table, T6 overhead | T1 ends; T2 starts |
| 5 | Code: rDefender's and ALFO's attacks, MAC-rotating and threshold-aware attackers on the testbed driver; you reinstall | T4 (14 h) |
| 6 | T4 report | T4 ends |
| 7 | Fetch univ1 if available; trace models | T5 (univ2, 9 h) |
| 8 | T5 report | T5 univ1 or T3 |
| 9 | Reruns of failed or invalid runs (slack) | reruns |
| 10 | All reports, brief, paper tables and figures | - |

## 7. What goes in the paper

- Table: T1 in the papers' format, final system against 8 configurations, with H1-H3.
- Ablation table: v2.1 alone, PortGuard alone, port vs host identity, + hold, local vs
  federated (H4, H5), + fair eviction.
- Fidelity table R0. Robustness: T4 (held out, H6), T5, T3. Overhead T6. Offline table E1.
- Figures: rule count, attack share and Packet-In over time (one T1 seed, A2 and adaptive);
  harm vs table size and idle timeout (T2).
- Limitations: no hardware; one controller per run on one host; G4 and P1 outcomes.

## 8. Topology (unchanged)

```
            srv (server)
             |
          s{k}1  core       table 3,500, monitored
          /     \\
     s{k}2       s{k}3      access switches, tables 3,500, monitored
    h1 h2 h5    h3 h4 h6    h5, h6 attackers (one per access switch)
```
