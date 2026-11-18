# One-host flash crowd on more seeds: preregistration

Drafted and fixed 18 November 2026, approved by the user and committed before any code below was
written and before any run. A follow-up to docs/flash2_prereg.md (round 2, results/testbed_flash2); it
changes none of round 2's or the sensitivity study's results.

## 1. Why

In round 2's one-host crowd (F2H), FEVER blocked the crowd host d1h3 in two of three runs (seeds 4187
and 4189) and failed F1 and F2. In the sensitivity study (docs/sensitivity_prereg.md) every one of
six changed settings blocked d1h3 in all three runs. Three seeds give only a rough idea of how often
FEVER blocks a host that sends a whole flash crowd. This study measures that rate on ten new seeds,
with FEVER as evaluated and no defense, and checks the exploratory reading of seed 4188 (s11 filled
more slowly in the first crowd, so FEVER did not block there).

## 2. Traffic and runs

- Exactly round 2's one-host case: T1B on tree3, benign scale 0.5, idle timeout 10 s, 1 s polls,
  new-connection probe on, 300 s runs, capacity 2,000 on all three switches, crowd rate F2 (round 2's
  selection, results/testbed_flash2/selection.txt; not selected again), every crowd flow from d1h3,
  three 12 s crowds per run drawn from the seed as in round 2. No attacker sends.
- Methods: no defense (none) and FEVER (fever-fl-ll), unchanged. The baselines are not run; none
  of them blocked a host in round 2.
- Seeds 4200-4209, used by no earlier run.
- 2 methods x 10 seeds = **20 runs**, about 1 h 50 min, plus one rerun pass. Names
  fc3_T1B_F2H_<method>_s<seed>. Order: by seed, then method (none first).
- Invalid runs: the campaign's rule as changed by amendment 1 (docs/final_campaign_prereg.md,
  section 11). An invalid run is rerun once with the same seed and listed in reruns.md; a run
  invalid twice is reported as missing.

## 3. Measures

As round 2 (testbed/summarize_run.py with --capacity 2000; testbed/analyze_flash2.py's definitions):
benign harm, lost first packets, new-connection success, benign hosts blocked (counted once per
host), benign entries deleted per minute, s11's and s13's largest poll, seconds s11 spent at or above
1,800 entries, the drop share of controller messages, and, for each block of d1h3, its time relative
to the crowds and the rule that blocked it (inferred as in round 2). Also, per run, s11's largest
poll during the first crowd.

## 4. What is reported (no pass rule; FEVER is not changed)

- **C1 (rate).** The number of FEVER's ten runs in which d1h3 was blocked, with an exact
  (Clopper-Pearson) 95 % interval; and the same pooled with round 2's three runs (13 runs).
- **C2 (harm).** FEVER's and no defense's mean benign harm over the ten seeds, and their paired
  difference per seed, as in round 2's F2; reported, not tested.
- **C3 (check of the seed-4188 reading).** s11's largest poll in the first crowd, compared between
  FEVER's runs with and without a block of d1h3. The reading is supported if every unblocked run
  peaks lower than every blocked run in the first crowd; otherwise it is reported as not supported.
  If FEVER blocks d1h3 in all ten runs or in none, C3 cannot be checked and is reported so.

Stated now: round 2 and the sensitivity study (20 of 21 runs blocked d1h3) lead us to expect blocks
in most of the ten runs, with harm well above no defense's. Whatever the result, the paper reports
it as the one-host crowd's rate; no FEVER setting or rule is changed for this study.

## 5. Files

- testbed/campaign_crowdseeds.sh: the 20 runs and one rerun pass (E5_CAP=2000, tag fc3), as
  testbed/campaign_flash2.sh without the selection. No change to the Ryu app, the traffic driver or
  the wrapper, so no reinstall is needed (to be confirmed against the installed snapshot before the
  first run).
- testbed/analyze_crowdseeds.py: results/testbed_crowdseeds/runs.csv and report.md, reusing
  testbed/analyze_flash2.py's measures.
- Afterwards, the paper, the results PDF and the findings summary updated with the rate.
