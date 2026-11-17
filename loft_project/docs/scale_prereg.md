# More colluding attackers on the testbed: preregistration

Fixed 17 November 2026, approved by the user and committed before any run. A
follow-up study after the final campaign (docs/final_campaign_prereg.md, section 5, held-out cells:
"more colluding attackers are the scalability study's subject"). It changes none of the campaign's
results.

## 1. Question

The campaign had two attackers. EVX showed that two attackers who each keep below FEVER's volume
limit get past its volume rule. How do FEVER and the baselines hold when 4 or 8 attackers collude,
each with its own host?

## 2. Setup

- T1B on the tree3 testbed at the campaign's settings: benign scale 0.5, capacity 3,500, idle timeout
  10 s, 1 s polls, new-connection probe on, 300 s runs, attack from 50 s.
- n attackers, alternating between the two access switches: h5, h7, ... on s12 and h6, h8, ... on
  s13. With n = 4 each access switch has two; with n = 8, four. Benign hosts h1 to h4 as before.
- Each attacker runs the attack's own schedule, as in the campaign; the attackers start together.
  - **G2:** each attacker opens up to 1,700 flows.
  - **EVX:** each attacker keeps at most 628 live flows, 0.8 times FEVER's lowest per-switch
    volume limit. Every attacker is below the limit on its own, while together they hold
    n × 628 entries on the core switch: 2,512 with n = 4 and 5,024 with n = 8.
- n = 4 and n = 8; seeds 4184, 4185 and 4186, used by no earlier run.
- n = 2 is the campaign itself (seeds 4160–4164). It is shown beside the new runs from
  results/testbed_prereg_final/runs.csv, and it is not rerun.

## 3. Methods and runs

- FEVER (fever-fl-ll), FTMaster, FTODefender and DMS-BTT (dms-btt-h1), with their campaign settings
  and models. FTODefender held G2 and EVX lowest in the campaign; FTMaster and DMS-BTT are the
  closest learning-based baselines.
- No defense is added at n = 8 only, to show how far the attack fills the table.
- 4 methods × 2 attacks × 2 attacker counts × 3 seeds = 48 runs, plus 6 runs without defense:
  54 runs in all, about 5 h.
- Named sc<n>_T1B_<attack>_<method>_s<seed>, ordered by seed, then attacker count, attack and method.
- Invalid runs: the campaign's rule with amendment 1. A run invalid twice is reported as missing.

## 4. Measures

As in the campaign, over the traffic window:
- attack occupancy (all attacker hosts);
- benign harm;
- new-connection success;
- lost first packets;
- attacker hosts blocked, and the time to the first and to the last block;
- benign hosts blocked;
- decision time and controller CPU.

## 5. Tests

- **S1 (G2).** FEVER's attack occupancy is lower than each baseline's in the seed-paired runs, over
  n = 4 and n = 8 together (6 pairs per baseline). A one-sided sign test per baseline, with Holm's
  correction over the three. Six wins out of six gives p = 0.016 before correction.
- **S2 (EVX).** No test: FEVER's occupancy and blocks are reported for n = 2, 4 and 8. Expected from
  the campaign, and stated now: FEVER does not block EVX attackers by its volume rule at any n, and
  its occupancy grows with n.
- **S3 (no false blocks).** FEVER blocks no benign host in any run. Pass or fail.

Nothing else is a claim.

## 6. Files

- testbed/run_testbed.py --attackers n (tree3);
- traffic_driver.py --n-attackers;
- summarize_run.py: attackers are hosts 5 and up;
- the wrapper accepts --attackers 2, 4, 6 or 8;
- testbed/campaign_scale.sh;
- testbed/analyze_scale.py: results/testbed_scale/runs.csv and report.md.
