# Deviations after the freeze of preregistration v3

The preregistration (preregistration.json, sha256 in preregistration.sha256) is unchanged; this
file logs what happened after it was frozen.

## D1. Seed 4120's first 18 runs discarded: testbed load from another application (2026-11-04)

- The campaign started at 18:46. A Zoom client had been open since 18:10, before the campaign
  started, and its webview used up to about 117 % CPU. With it, the 4-core laptop ran at load
  average 9 with about 2 % idle CPU (Open vSwitch and the Ryu controller each on a full core).
- Symptom, the same for every defense, none included: after the attack start, benign lost first
  packets were 12-29 % and probe success about 30 %. The matching smoke run of the day before
  (A2, ensguard, scale 0.5, idle laptop) lost 2.08 % with 64 % probe success.
- Why discarded: G0 (benign-only, idle laptop) holds only for the load it was calibrated at;
  these runs measure an overloaded host rather than the defenses. The decision rests on the
  load and on the no-defense runs, which no defense can affect.
- Action: the campaign was stopped at 20:23 during run 18 of 40 (A4, rdefender). All 18 run
  directories were renamed in place to `_invalid_load_zoom_v3_T1_*_s4120` and are excluded
  from every analysis. The campaign restarts from the first run of seed 4120, unchanged
  (same script, hash 12ebc74b...), with no other application open.
- From here on, the laptop runs nothing but the testbed during the campaign.
