# FEVER with ingress blocking (amendment 2 of the deployed configuration)

*Fixed 9 November 2026, before any run with the change.*

## Why

In the deployment check's Aware (E9P) runs (seeds 4181-4182, fever-fl-ll), FEVER blocked the two
attackers (h5, h6) at the core switch s11 only, 75-81 s after the attack started. Their access
switches s12 and s13 never blocked them:

| Run | Attack rules installed at s12 + s13 | Attack Packet-Ins refused at s11 | Attack share, s12 / s13 (mean after onset) |
|---|---|---|---|
| 4181 | 5,716 after the block | 10,116 | 39.3 % / 40.4 % |
| 4182 | 15,035 over the run | 50,081 | 27.1 % / 27.0 % |

The block at s11 was a 2 s drop rule on the host's MAC, renewed at every 1 s poll. The controller
was saturated from about 80 s to the end (Ryu at 100 % of a core, event queue at 114 of 128,
63,123 messages to it dropped by Open vSwitch in run 4181); the likely reason for the refused
attack Packet-Ins is that renewals came late and the rule lapsed (not confirmed).

## Change

A host FEVER blocks (blocks are permanent since v6) is dropped at its own access port: one
permanent rule matching that port, above the per-flow rules, on the host's access switch (the
port that port security pinned to its MAC). Nothing from the host then reaches any table or the
controller. The blocking switch keeps its renewed 2 s rule only until the ingress rule is in place
(sent 1.5 s ago with no TABLE_FULL error), or when the host's port is unknown. Everything else is
fever-fl-ll as deployed (amendment 1 of docs/testbed_training_plan.md): detector, threshold, rule A,
volume rule. The old behaviour stays available as fever-fl-ll-noing.

The same day the baselines' source blocks were moved into the switch as their papers describe
(docs/final_campaign_prereg.md, section 4); that change does not touch FEVER.

## Development check (testbed)

T1B at 600 pps (benign scale 0.5), tree, 300 s, attack at 50 s, probe on. fever-fl-ll (ingress)
and fever-fl-ll-noing (old) on A2, A4, E9P and benign, development seeds 4181-4182, both arms run
now on the same snapshot: 16 runs. Also FTMaster on E9P, seeds 4181-4182 (2 runs), only to check
that its source blocks now install drop rules; not part of the rule below. 18 runs, about 2.3 h.

Ingress blocking is adopted only if all hold (means over the two seeds):

| Check | Condition |
|---|---|
| A2, A4, E9P, each | harm of ingress <= old + 0.1 point, and attack occupancy (mean of s11-s13) <= old + 2 points |
| Innocent hosts | no benign host blocked by ingress in any run |
| Benign only | harm of ingress <= 0.1 % |

If any fails, FEVER stays fever-fl-ll-noing and the result is reported. Reported regardless (not
tests, two seeds): new-connection probe success after onset, benign flows never installed, Packet-Ins,
drop rules, ingress rules, first attacker block. Analysis: testbed/analyze_ingress.py, writing
results/tbfl/ingress_check.md.

## Then

If adopted, the final campaign's FEVER (fever-fl-ll) and its ablations block at the ingress, and
"FEVER without ingress blocking" (fever-fl-ll-noing) is added to the ablations of the
preregistration draft before it is fixed.
