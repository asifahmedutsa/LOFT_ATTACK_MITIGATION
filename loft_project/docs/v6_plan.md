# FEVER with permanent blocking (v6)

*Fixed 2026-11-07, before any v6 result.*

## Change

FEVER v5 blocks a host for 60 s, doubling on each repeat to at most 240 s, then releases it. Under
A2 every testbed run showed the same pattern: the block expires, the attackers return, and the table
fills to 70-92 % before the re-block; this refill is all of FEVER's A2 harm
(results/paper_figs/v5/fig16_a2_block_expiry, fig20_malicious_share_A2).

v6 changes one setting: **a blocked host stays blocked** (no expiry), as in FTMaster, FTODefender,
FloRa and ALFO-Guard. Everything else is v5: detector, tau, eviction, block rules A and B, volume
limit X, PortGuard.

## Development check (simulator, before any testbed run)

Simulator, test-domain traffic T1B at the testbed's 600 pps, development seeds 2000-2002, attacks
A2, A4, E9P and benign only; v5 and v6 on the same episodes (each host on its own port).

v6 is adopted only if all hold:

| Check | Condition |
|---|---|
| A2 | mean harm of v6 <= v5 and mean attack occupancy of v6 <= v5 |
| A4, E9P | mean harm of v6 <= v5 + 0.1 point and mean attack occupancy <= v5 + 2 points, each attack |
| Innocent hosts | no benign host blocked by v6 in any episode |
| Benign only | mean harm of v6 <= 0.1 % |

If any fails, FEVER stays v5 and the result is reported.

## Then

1. The user reinstalls (controller defense ensguard-v6, results/v21/exported/ens_config_v6.json).
2. Testbed: v6 x A2, A4, E9P, benign x seeds 4140-4144 (the seeds of the v5 campaign, so v6 and
   v5 pair run by run), 20 runs. Reported as a follow-up to the preregistered v5 campaign, with
   the v5 result unchanged.
