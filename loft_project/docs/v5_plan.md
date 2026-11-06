# EnsGuard v5: clean T1 split, real-traffic training, local + federated detection, volume block

*Fixed 2026-11-06, before any v5 data was collected or any v5 model was trained.*

## Why

**Train/test overlap on T1.** bigFlows is a 5-minute capture, and every seed replays it from a
different offset. As a result:
- the T1 training runs (seeds 1000-1004) and the testbed test runs replayed the same benign
  flows;
- the baselines' T1 models (DMS-BTT, FTMaster) have seen the test traffic, and so have the
  EnsGuard thresholds calibrated on T1.

v5 removes this overlap and adds two changes aimed at the remaining gaps:
- A2 harm, where the T1-trained baselines lead;
- A4/E9P, which every detector misses.

## 1. Clean split of the trace (applies to every defense)

| Domain | Trace window | Use |
|---|---|---|
| **T1A** | first 40 % of the bigFlows span | all T1 training and calibration, for every defense |
| **T1B** | last 60 % of the bigFlows span | testbed test traffic, plus simulator development checks on development seeds |

- **Why 40 %, not half (fixed from packet counts alone, before any result):** a flow counts in
  the part that holds its first packet, and bigFlows' long flows start early, so a 50 % split
  leaves T1B only 158k packets: less than one 300 s pass at the testbed's 600 pps. At 40 %:
  - T1A keeps 339k packets, a 283 s pass at 1,200 pps (training runs are 240 s);
  - T1B keeps 206k packets, a 343 s pass at 600 pps.

  Simulator checks on T1B run at 600 pps, the testbed's rate.
- **Flow assignment.** A flow belongs to the half that contains its first packet; its packets in
  the other half are dropped. Replays wrap inside their own half.
- **Same setup otherwise.** Both domains keep T1's hosts, attacker addresses (domain index 3) and
  rate.
- **Models the testbed deploys for domain T1B** are all trained or calibrated on T1A:
  - DMS-BTT: state and flow models (A1-A3 + benign, training seeds 1000-1004);
  - FTMaster: state and rule models (same data, E2 hyperparameters);
  - EnsGuard (v3, v4-lite, v5): tau on T1A validation benign (seeds 2000-2002).
- **T1B is never trained or calibrated on.**

## 2. v5 detector candidates

The CatBoost federation and the 0.1 % benign budget are kept from v4-lite.

| Candidate | Federated part | Local part on the T1B controller |
|---|---|---|
| A | CatBoost, D1-D3 (= v4-lite) | none |
| B | CatBoost, D1-D3 | local CatBoost trained on T1A (benign + A1-A3); evict if federated >= tau_f OR local >= tau_l, with tau_f and tau_l each at a 0.05 % budget on T1A validation benign |
| C | CatBoost, D1-D3 + U2 | none |
| D | CatBoost, D1-D3 + U2 | as B |

**U2** is a new client: real univ2 benign traffic (T2) plus A1-A3, training seeds 1000-1004,
CatBoost, shared like D1-D3. Its tau for T2 is set on T2 validation benign. A4, E9P and A6 stay
out of every training set.

**Measures.** All data are data no candidate trained on.
- **R-A4, R-A2, R-E9P:** per-entry recall on simulator T1B, attacks A2, A4 and E9P, development
  seeds 2000-2002 (5 % of entries per poll), at the candidate's tau.
- **FPR:** per-entry false-positive rate on simulator T1B benign, development seeds 2000-2002.
- **R-unseen:** E11 recall on the attack no controller saw (A6), D1-D3 test_off, at the 0.1 %
  point (B and D: the federated part only; the local part exists only on the T1B controller).

**Rule.**

| Condition | Bar |
|---|---|
| FPR | <= 0.2 % |
| R-unseen | >= 46.5 % (v3: 48.5 %) |
| R-A2 | >= R-A2 of A - 1 point |

- **Choice:** among the candidates that meet every condition, the highest R-A4 + R-E9P.
  Candidates within 2 points of the best tie, and a tie goes to the simplest (A, then B, C, D).
- **If none meets every condition,** candidate A (v4-lite's detector) is kept.

## 3. Volume block (a second, detector-independent block rule)

**The rule.** A host is blocked (60 s, doubling, at most 240 s, as now) when, at a poll with the
table >= 90 % full, both hold:
- it holds more than X entries;
- it holds at least 3 x the median host's entries.

X is calibrated per switch as 1.5 x the largest number of entries any benign host holds in that
switch's own T1A benign recordings.

**Calibration data:** 3 new testbed recordings of T1A benign traffic (seeds 4150-4152, defense
none, entry log), at the testbed's rate.

**Check data:**
- 3 testbed recordings of T1A attacks (A2, A4, E9P, seed 4153, defense none);
- the simulator T1B closed loop (development seeds) is not used, because its per-host rates differ
  from the testbed's.

**Rule.** The volume block is adopted only if both hold:
- on the calibration recordings, replayed open loop, it would block no benign host;
- on the attack recordings, replayed open loop, it would block both attackers in at least 2 of the
  3 runs.

Otherwise it is left out.

## 4. Then

1. The user reinstalls once, after the T1A/T1B code and every T1B model are exported.
2. Testbed development check: the chosen v5, A4 and benign on T1B, seeds 4134-4136.
3. A new preregistration replaces preregistration_v4lite before any test run:
   - defenses: none, ensguard (v3), ensguard-v4lite, ensguard-v5, dms-btt, ftmaster;
   - traffic: T1B, A2, A4, E9P and benign;
   - fresh seeds 4140-4144: 120 runs, about 11 h;
   - hypotheses as in v4-lite, H1-H7, for v5 against v3 and against DMS-BTT and FTMaster.
4. No test seed runs before the user approves the preregistration.

## Result of section 2, and univ2 dropped (2026-11-06)

**Candidate A is kept** (results/v5/cands.md). This is v4-lite's detector: CatBoost, D1-D3.
- No candidate detects A4 or E9P on simulator T1B.
- The univ2 client (C, D) cuts recall on the unseen attack from 51.0 % to 8.6 %.
- The local T1A model adds 0.5 points of A2 recall, within the tie margin.

**univ2 is dropped from v5 by the user's decision.** It is not a client of any deployed model and
not part of the campaign. Its only remaining use is a possible later, separate test on univ2
traffic.
