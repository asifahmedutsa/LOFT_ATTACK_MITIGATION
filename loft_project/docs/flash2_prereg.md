# Flash crowds, round 2: preregistration

Drafted and fixed 17 November 2026, approved by the user and committed before any code below was
written and before any run. A follow-up to docs/flash_prereg.md (round 1, results/testbed_flash); it
changes none of the campaign's or round 1's results.

## 1. Why a second round

Round 1 asked whether FEVER blocks a benign host when benign traffic fills the flow table. The crowds
were sent as scheduled (about 500 new flows per second at k = 8), but the table never filled: s11
peaked at 2,458 to 2,756 of 3,500 entries. The cause is the controller, not the traffic generator.
Ryu received about 630 Packet-Ins per second outside the crowds and only about 700 during them;
Open vSwitch dropped the messages the controller did not read in time (coverage counter
rconn_overflow). In the 24 round-1 runs the switches
dropped 18 % to 29 % of their controller messages, so most crowd flows never received an entry, and
the low new-connection success (about 58 % with no defense) and the 20 % lost first packets came
from this overload. FEVER's volume rule, which acts only at 90 % occupancy, was never exercised.

Round 2 keeps the controller below its limit and makes the table small enough for the crowds to
fill it, and adds the case a per-host volume rule is most likely to get wrong: a crowd from one host.

## 2. Traffic

- T1B on the tree3 testbed at the campaign's settings (benign scale 0.5, idle timeout 10 s, 1 s polls,
  new-connection probe on, 300 s runs), except the table capacity: **2,000 entries** on all three
  switches (round 1 and the campaign: 3,500). FTMaster and rDefender evaluate at 2,000 entries,
  FloRa at 1,500 to 3,000. No attacker sends; h5 and h6 stay silent.
- Crowds as in round 1 (loftbench/trace.py, flash_crowds): three per run, 12 s each, start drawn
  uniformly between 20 and 283 s, new short flows (about 5 packets, 50 ms apart) at k times the
  replay's new-flow rate, sources from 192.0.0.0/12.
- Two placements, the same crowds otherwise (same seed, same schedule):
  - **Spread (F<k>)**: crowd flows spread over the four benign hosts by source address, as in round 1.
  - **One host (F<k>H)**: every crowd flow is sent by d1h3, on access switch s13. The ping (d1h1)
    and the new-connection probe (d1h2) are on s12 and unaffected by where the crowd enters.
- Seeds 4187, 4188 and 4189, used by no earlier run.

## 3. Crowd rate, by a rule fixed now

Selection runs: no defense, spread placement, seed 4187, tag fl2sel, capacity 2,000, for k = 2, 3, 4, 5
and 6 in turn. For each run:
- fill: s11's largest poll is at least 1,800 entries (90 % of 2,000);
- drop share: rconn_overflow / (rconn_queued + rconn_overflow) over the run, summed over the three
  switches, from ovs_coverage_before/after.txt.

The study uses the first k that fills with a drop share of at most 10 %. If no k does, it uses the
first k that fills and reports its drop share; if none fills, k = 6, reported as not filled. Both
placements use the selected k. Selection runs are not results.

Expected from round 1 (capacity 3,500): k = 4 peaked at 1,867 entries with 7.6 % dropped, k = 6 at
2,434 with 14.0 %, so k = 4 is the likely choice.

## 4. Methods and runs

- No defense, FTMaster, FTOP, FTODefender, FloRa, DMS-BTT (dms-btt-h1) and rDefender with their
  campaign settings and models, and FEVER (fever-fl-ll), unchanged. FEVER's volume limit X stays as
  calibrated at 3,500 entries (799.5, 784.5 and 796.5 entries on s11, s12 and s13).
- 8 methods × 3 seeds × 2 placements = 48 runs, named fc2_T1B_F<k>[H]_<method>_s<seed>, plus up to
  five selection runs. Order: by seed, then placement (spread first), then method. About 4.5 h.
- Invalid runs: the campaign's rule with amendment 1; one rerun pass; a run invalid twice is
  reported as missing.

## 5. Measures

Per run (testbed/summarize_run.py with --capacity 2000, as round 1), and new in round 2:
- benign harm (%), lost first packets (%), new-connection success (%);
- benign hosts blocked (host blocks and ingress drops), benign entries deleted per minute,
  Table-Full messages;
- s11's largest poll and the seconds s11 spent at or above 90 % (1,800 entries);
- **new:** the drop share of controller messages (section 3);
- **new, one host:** whether d1h3 was blocked, at what time relative to the crowd, and by which of
  FEVER's rules. The log records the block, not the rule; the rule is inferred from the blocking
  switch's state at that poll: the volume rule if the table was at least 90 % full and d1h3 held more
  than X entries and at least three times the median host's; otherwise the eviction rule.

## 6. Pass rules for FEVER (the only claims)

For each placement separately:
- **F1.** FEVER blocks no benign host in any of its three runs.
- **F2.** FEVER's mean benign harm over the three seeds is at most 1.0 point above no defense's.

The baselines' numbers are reported, not tested. Three seeds, no significance test.

Stated now: in the one-host placement, d1h3 will hold far more entries than the other hosts. If s11
or s13 reaches 90 %, FEVER's volume rule is likely to block it, and FEVER would fail F1 and probably
F2. That outcome is reported as it is; FEVER is not changed for this study.

## 7. Files

- testbed/traffic_driver.py: a trailing "H" on an F variant sends every crowd flow from benign
  host 2 (d1h3). Benign packets of the replay are unchanged. Needs testbed/root/install.sh (run by the
  user) before any run.
- testbed/campaign_flash2.sh: selection, then the 48 runs and one rerun pass (E5_CAP=2000).
- testbed/analyze_flash2.py: results/testbed_flash2/runs.csv and report.md, with the drop share, the
  one-host block analysis, and round 1's drop shares for comparison.
- Afterwards, the corrected explanation of round 1 in paper/main.tex and
  docs/build_results_section.py, and round 2's results beside it.
