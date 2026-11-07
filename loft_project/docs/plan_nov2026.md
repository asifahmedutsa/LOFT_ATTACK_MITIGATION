# FEVER: plan for 9-15 November 2026 (risks 1-4), then to NetSoft 2027

Decided 8 Nov: no Scapy (the current raw-socket generator stays, documented and validated against
the papers' fill times); risks 1-4 this week; final campaign with 3 seeds.

| Risk | Level | This week |
|---|---|---|
| 1. FEVER's detector trained on simulated traffic; baselines on real traffic | High | Mon-Tue |
| 2. Baselines not checked against their own papers | High | Tue-Wed |
| 3. v6 result on reused seeds | Medium | Wed night-Thu (final campaign) |
| 4. "Is it really federated learning?" | Medium | Tue (Flower, multi-round) |

## Mon 9: real-traffic training data
- Controllers: C1 univ2 parts 0-2, C2 univ2 parts 3-5, C3 bigFlows T1A (the test network's own controller).
- Attacks per controller: C1 G1 + Mimic, C2 G2 + Spoof, C3 G3 + Pulse; Slow and Aware seen by no one.
- Replayed in the simulator (as the baselines' T1A training data was), labelled rule rows per poll.
- univ2 replay rate set so its benign table load matches bigFlows.
- Before any training: the rule that picks FEVER's detector, written and committed.

## Tue 10: federated learning on real traffic (risks 1, 4)
- Flower, multi-round: federated XGBoost (bagging) and FedProx (neural network).
- Compared with: local only (the no-sharing ablation), one-shot sharing, pooled data.
- Exposure test on bigFlows T1B rows and held-out univ2 part 6: seen locally, seen only by another
  controller, seen by no one; recall, precision, F1 at 0.1 % false alarms.
- Detector chosen by Monday's rule.

## Tue 10 - Wed 11: faithful baselines (risk 2)
- DMS-BTT as published (no added blocklist, paper thresholds); the strengthened version reported beside it.
- rDefender reacting per refused request (event-based), not per poll.
- FTODefender trained on T1A and checked.
- Port features restored (FTMaster DDoP/CDD, FTOP IPs/ports, FTODefender VGFSP/VGFDP) where the
  replayed traces carry ports; otherwise listed as deviations.
- Each baseline run once in its own paper's setting (simulator) and compared with its reported numbers.

## Wed 11: deployment and preregistration
- Controller reads the chosen detector; development check on development seeds.
- Final campaign preregistered: hypotheses pooled over the five attacks (15 pairs per comparison),
  per-attack results as means and ranges.
- User reinstalls the testbed.

## Wed 11 night - Thu 12: final campaign (risk 3), fresh seeds 4160-4162
- Methods: none, FTMaster, FTOP, FTODefender, FloRa, DMS-BTT (as published), rDefender, FEVER.
- Traffic: G2, Mimic, Aware, Spoof, Pulse, normal only. 8 x 6 x 3 = 144 runs.
- Ablations: FEVER without sharing, without the volume rule, without the detector; G2, Mimic, Aware
  x 3 seeds = 27 runs.
- 171 runs, about 15 h, one at a time.

## Fri 13 - Sun 15: analysis, tables, figures; reruns of any failed run

## After this week
- Week of 16 Nov: live federation (Flower server plus controller processes over the network).
- Week of 23 Nov: scalability (3 -> 6 -> 9 controllers; 2 -> 4 -> 8 attackers, colluding below the
  volume limit; more hosts).
- 30 Nov - 10 Jan: figures, writing, supervisor review.
- 11-24 Jan: revisions, artifact, submission (NetSoft 2027 deadline to be confirmed).

## Fallbacks
- Federated XGBoost worse than one-shot sharing: FEVER keeps one-shot sharing; FL reported as comparison.
- A baseline cannot match its paper: report the mismatch and its likely cause.
- A close per-attack comparison that matters: 2 more seeds for that attack only, labelled as added.

## Needed from the user
- Reinstall on Wed 11.
- Laptop free from Wed 11 evening to Thu 12 evening (lid open, AC, no Zoom or Chrome).
- Ask the supervisor about a lab server; confirm the NetSoft deadline.
