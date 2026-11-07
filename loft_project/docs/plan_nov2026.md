# FEVER: schedule to NetSoft 2027 (from 8 November 2026)

Order follows the publication risks, highest first. Testbed runs: one at a time, overnight where long.
Exact NetSoft 2027 deadline to be confirmed (expected late January).

| Risk | Level | Addressed in |
|---|---|---|
| FEVER's detector trained on simulated traffic; baselines on real traffic | High | Weeks 1-2 |
| Baselines not checked against their own papers | High | Weeks 2-3 |
| v6 result on reused seeds | Medium | Week 4 (final campaign, fresh seeds) |
| "Is it really federated learning?" | Medium | Week 2 (federated XGBoost), week 5 (live) |
| No scalability results | Medium | Week 5 |
| Attack tool (Scapy) | Low | Week 1 |

## Week 1 (9-15 Nov): real traffic and Scapy
- Mon-Tue: Scapy attack generator; offline check of packets and timing; speed check. User reinstalls the testbed.
  Testbed check: no defense x G2, Mimic, Aware, Spoof, Pulse x 2 seeds (10 runs, ~1 h).
- Tue: no-sharing ablation on the existing benchmark (each controller's own model only), offline.
- Wed-Thu: real-traffic controllers. C1 univ2 parts 0-2, C2 univ2 parts 3-5, C3 bigFlows T1A; replay rates
  set so benign load matches; labelled data collection with Scapy attacks
  (C1 G1 + Mimic, C2 G2 + Spoof, C3 G3 + Pulse, plus normal; 5 seeds; ~54 runs, ~5 h, overnight).
- Gate (Fri 13 Nov): Scapy passes (time to full table within about 10 %); data collected.

## Week 2 (16-22 Nov): federated training on real traffic
- Flower: federated XGBoost (bagging) and FedProx; plus local only, one-shot sharing, pooled data.
- Evaluation by exposure on bigFlows T1B rows and the held-out univ2 part 6.
- Rule fixed in advance for which detector FEVER uses; decision on 20 Nov.
- Start baseline fixes: port features restored (FTMaster, FTOP, FTODefender), DMS-BTT original version,
  FTODefender trained on T1A, rDefender per refused request.

## Week 3 (23-29 Nov): faithful baselines and the new FEVER
- Each baseline once in its own paper's setting, compared with its reported numbers.
- Controller reads the new model; development check on development seeds. User reinstalls.

## Week 4 (30 Nov-6 Dec): final campaign (preregistered, fresh seeds 4160-4164)
- Methods: none, FTMaster, FTOP, FTODefender, FloRa, DMS-BTT (original), rDefender, FEVER.
- Attacks: G2, Mimic, Aware, Spoof, Pulse, plus normal only. 8 x 6 x 5 = 240 runs, ~21 h (3 nights).
- Ablations: FEVER without sharing, without volume rule, without detector (45 runs, ~4 h).

## Week 5 (7-13 Dec): live federation and scalability
- Live: Flower server plus 3 controller processes; rounds, bytes, time.
- Controllers 3 -> 6 -> 9 (more univ2 and bigFlows slices), offline.
- Testbed: attackers 2 -> 4 -> 8, including colluding attackers below the volume limit; hosts 6 -> 12 (~30 runs).

## Week 6 (14-20 Dec): analysis, figures, tables; reruns if needed

## Weeks 7-9 (21 Dec-10 Jan): paper writing; supervisor review

## Weeks 10-11 (11-24 Jan): revisions, artifact, submission

## Fallbacks
- Federated XGBoost worse than one-shot sharing: FEVER keeps one-shot sharing; FL reported as comparison.
- Laptop cannot run the larger topologies: scalability offline plus the sizes the laptop handles; ask for a server.
- A baseline cannot be made to match its paper: report the mismatch and its likely cause.

## Needed from the user
- Reinstall the testbed after week 1 day 2 and in week 3.
- Laptop free (lid open, AC, no Zoom or Chrome) on run nights: 11-12 Nov, 25-26 Nov, 1-4 Dec, 9-10 Dec.
- Ask the supervisor about a lab server; confirm the NetSoft deadline.
