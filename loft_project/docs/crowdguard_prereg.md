# Telling flash crowds from attacks (crowd guard): preregistration

Drafted and fixed 18 November 2026, approved by the user and committed before any code below was
written and before any testbed run. A follow-up to the flash-crowd studies
(docs/flash_prereg.md, docs/flash2_prereg.md); it changes none of the earlier results, and FEVER as
evaluated in the campaign stays FEVER.

## 1. Why

In round 2 with the crowd sent by one host (F2H), FEVER blocked that benign host: seed 4187, d1h3
blocked at 284 s, 11 s into a crowd, by the eviction rule (s11 at 87 %, d1h3 holding 1,085 entries
against a median host's 182). The detector flags the crowd's short new flows, the host's evictions
become an outlier, and the host is blocked. FEVER's harm in that run was 3.27 % against 0 % without a
defense. (Round 2's full results are in results/testbed_flash2 once the campaign ends.)

## 2. The signal

A low-rate attacker can hold an entry cheaply only by refreshing it: it sends again before the idle
timeout (10 s), over and over. All seven attacks do so (gaps of 2 to 9.8 s). A flash-crowd flow sends a
few packets (about 5, 50 ms apart) and stops. An attacker that stops refreshing must open new flows at a
much higher rate to keep the table full, which is a high-rate flood visible in the Packet-In rate.

The signal is measured per flow (5-tuple), not per entry, because FEVER evicts flagged entries: an
evicted attack flow reappears at its next refresh as a new Packet-In, so per entry the controller
might never see a refresh. Definition: a flow is **refreshed** when the controller sees a packet of it
(a counter rise at a poll, or a Packet-In) at least 2 s after its previous packet and less than 10 s
after it. A host's **refresh share** is the share of its flows seen in the last 30 s that were
refreshed at least once.

## 3. Gate G0: an offline check before any code (loftbench/crowd_signal.py)

On the exact schedules the testbed sent (T1B, benign scale 0.5; round 2's crowds, seed 4187, and the
campaign's seven attacks, seed 4160), extended to compute the refresh share per host over sliding
30 s windows:
- crowd host (F2H, d1h3) during each crowd and the 10 s after it: largest refresh share at most 0.3;
- each attacker host, from 20 s after the attack starts to the end: smallest refresh share at least 0.7,
  for every one of the seven attacks.

If G0 fails, the study stops here and the result is reported; no FEVER variant is built.

## 4. The variant: FEVER-G (fever-fl-ll-guard)

FEVER unchanged (detector, tau, rho = 70 %, eviction, both block rules, ingress blocking), plus:
- **Guard.** Before either block rule blocks a host, the host's refresh share must be at least
  **0.5**. Otherwise the host is not blocked.
- **Crowd response.** A host that a block rule selects but the guard stops is put in crowd mode for
  30 s (renewed while the rule keeps selecting it): at each poll, FEVER deletes that host's entries
  whose counters did not change for 2 polls (finished flows) instead of blocking the host. The
  controller logs a crowd_host event (time, host, switch, refresh share).
- The thresholds (2 s, 10 s, 30 s window, 0.5, 30 s crowd mode, 2 polls) are fixed here and not tuned
  on any testbed run.

## 5. Runs

Testbed and settings as in each source study; FEVER-G only (the other methods' results are reused, run
for run, from the same seeds):
- **Crowds (round 2 settings):** capacity 2,000, F2 and F2H, seeds 4187-4189: 6 runs, paired with
  round 2's FEVER and no-defense runs.
- **Attacks (campaign settings):** capacity 3,500, T1B, G2, Spoof and Pulse with seeds 4160-4162,
  Mimic, Aware, Slow and EVX with seeds 4160-4164: 29 runs, paired with the campaign's FEVER runs.
- 35 runs, about 3.1 h, plus one rerun pass. Names cg_T1B_<variant>_fever-fl-ll-guard_s<seed>.
  Invalid runs: the campaign's rule with amendment 1. UHt is not run.

## 6. Pass rules (no significance tests; three to five seeds)

- **C1 (crowds).** FEVER-G blocks no benign host in any of its 6 crowd runs, and its mean harm in each
  placement is at most 1.0 point above no defense's (round 2).
- **C2 (attacks, not worse than FEVER).** For each of the seven attacks, FEVER-G's mean occupancy is
  at most 2 points above FEVER's, and its mean harm at most 0.1 point above FEVER's. Each attack
  passes or fails on its own.
- Reported beside them: first-block time per attack against FEVER's, crowd_host events in the attack
  runs (a guard that stops a real attacker shows up here), and the refresh share at each block.

Stated now: the guard can delay blocks, since a host's refresh share needs time to build up after an
attack starts; Pulse (on 60 s, off 30 s) and Slow (gaps up to 9.8 s, close to the 10 s timeout) are
the attacks most likely to fail C2.

## 7. Files

- loftbench/crowd_signal.py: G0 (extended to per-host windows).
- loftbench/defenses.py: EvictBlock option guard (refresh tracking per flow, the guard and crowd
  mode); testbed/loft_ryu_app.py: method fever-fl-ll-guard; testbed/root/loft-testbed: accept it.
  Needs install.sh (run by the user) before any run.
- testbed/campaign_crowdguard.sh, testbed/analyze_crowdguard.py: results/testbed_crowdguard.
