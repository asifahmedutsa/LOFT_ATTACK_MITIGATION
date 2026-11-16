# Flash crowds on the testbed: preregistration

Fixed 17 November 2026, before any flash-crowd run. A follow-up study after the final campaign
(docs/final_campaign_prereg.md); it changes none of the campaign's results. Design choices were
approved by the user on 17 November (burst size, methods, pass rule).

## 1. Question

FEVER blocks hosts permanently. When benign traffic alone fills the flow table, does FEVER block a
benign host, or harm benign flows more than no defense does? The six baselines are run under the
same traffic and reported beside it. FTOP's paper evaluates flash crowds in the same way.

## 2. Traffic

- T1B on the tree3 testbed at the campaign's settings: benign scale 0.5 (600 packets/s), capacity
  3,500, idle timeout 10 s, 1 s polls, new-connection probe on, 300 s runs. No attacker sends; the
  attacker hosts h5 and h6 stay silent.
- Variant F<k> (loftbench/trace.py, flash_crowds): on top of the T1B replay, exactly three crowds per
  run. Each crowd lasts 12 s and starts at a time drawn uniformly between 20 and 283 s. A crowd adds
  new short flows at k times the replay's own new-flow rate. Flow sizes follow the generator's
  flash kind: about 5 packets, 50 ms apart. Sources are drawn from 192.0.0.0/12. The flows spread
  over the four benign hosts by source address, as the replay's flows do.
- Seeds 4165, 4166 and 4167, used by no earlier run.

## 3. Burst size, by a rule fixed now

- The crowd must fill the core table: under no defense, s11 must reach at least 90 % of its capacity
  (3,150 entries) at some poll.
- One selection run under no defense, seed 4165, tag flsel, is made with k = 4.
  - If s11's largest poll reaches 3,150 entries, k = 4.
  - Otherwise the run is repeated with k = 6, then k = 8, and the first k that passes is used.
  - If k = 8 fails, the study runs at k = 8 and reports that the table was not filled.
- Selection runs are not results.
- An offline estimate from the traffic schedule (idle timeout 10 s, no defense) puts the live
  benign entries at 3,611 to 4,085 at k = 4 for the three seeds, against 1,675 to 1,815 without
  crowds.

## 4. Methods and runs

- No defense, FTMaster, FTOP, FTODefender, FloRa, DMS-BTT (dms-btt-h1, as amendment 3) and
  rDefender, all with their campaign settings and models, and FEVER (fever-fl-ll), unchanged.
- 8 methods × 3 seeds = 24 runs, named fc_T1B_F<k>_<method>_s<seed>.
- Order: by seed, then method.
- Invalid runs: the campaign's rule with amendment 1. A run invalid twice is reported as missing.

## 5. Measures

Per run, from testbed/summarize_run.py:
- benign harm (%);
- lost first packets (%);
- new-connection success (%);
- benign hosts blocked;
- benign sources blocked;
- benign entries deleted per minute;
- Table-Full messages;
- s11's largest poll (entries) and the seconds s11 spent at or above 90 % of capacity.

## 6. Pass rule for FEVER (the only claim)

- **F1.** FEVER blocks no benign host in any of its three runs: hosts_blocked_benign = 0, and no
  ingress block of a benign host.
- **F2.** FEVER's mean benign harm over the three seeds is at most 1.0 point above no defense's.

Each part passes or fails. The baselines' numbers are reported, not tested. With three seeds, no
significance test is made. If FEVER fails F1, the report gives the blocked host, the time and the
rule that blocked it.

## 7. Files

- testbed/campaign_flash.sh: selection, then the 24 runs and one rerun pass.
- testbed/analyze_flash.py: results/testbed_flash/runs.csv and report.md.
