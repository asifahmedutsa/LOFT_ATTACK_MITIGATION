# Post-hoc diagnosis of ensguard on the v3 T1 testbed runs

**Status: exploratory, not preregistered.** Written on 2026-11-05 while seed 4124 was still
running, from the finished runs of seeds 4120-4123, and updated on 2026-11-06 with seed 4124
after the campaign ended (`testbed/diagnose_v3.py`, which only reads existing run directories).
The preregistered result is in `report.md` (`testbed/analyze_v3.py`). Nothing here changes the preregistered analysis, the frozen
system or the campaign. Any fix proposed below needs a new preregistration and fresh seeds.

## What failed

Final, all 15 paired attack runs (`report.md`): H1 (lower benign harm than each comparator) is
supported against none of the 8 comparators; H2 (lower attack share at s11) against evict, SIFT
and TableGuard only; H3 passes; H4 (no benign host blocked) failed in 4 of 20 runs:

| Run | Benign host blocked | Harm |
|---|---|---|
| A4, seed 4122 | d1h4 at 270.6 s | 12.41 % |
| A4, seed 4123 | d1h1 at 195.4 s | 8.11 % |
| A2, seed 4123 | d1h2 at 226.0 s (after both attackers were blocked) | 9.69 % |
| A4, seed 4124 | d1h4 at 222.6 s, d1h2 at 244.0 s | 10.83 % |

## Finding 1: on the testbed, the detector barely fires under the mimicry attacks (A4, E9P)

The s11 deletes split by regime: "PortGuard on" means the table reached 90 % in the last 31 s;
"detector only" means the table is 70-90 % full and only the detector acts.

| Attack | Attacker entries deleted while only the detector acts | Benign entries deleted then | Attacker entries deleted while PortGuard is on |
|---|---|---|---|
| A2 | 6,000-13,600 per run | 46-68 | 0-51,000 |
| A4 | **4-10 per run** | 30-188 | 390-4,700 |
| E9P | **0** | 4-74 | 5,600-8,200 |

(Seed 4124: A2 11,539 / 43 / 5,028; A4 7 / 188 / 4,742; E9P 0 / 9 / 5,774. Same pattern.)

- **A2** (fixed source, default packet sizes): the detector works. It evicts thousands of
  attacker entries, blocks both attackers within about 65-75 s of the attack start, and its
  precision in the detector-only regime is about 99 %.
- **A4 and E9P** (benign-sized packets, 1-3 packets per refresh, source pool): the detector flags
  almost nothing.
  - Its precision in the detector-only regime falls to roughly 5-15 %; most of its flags are benign entries.
  - All removal of attacker entries comes from the PortGuard fair-share fallback.
  - That is why the attack share at s11 stays near "none": A4 46 % vs 53 %, E9P 61 % vs 68 %.
  - Neither attacker is ever blocked.
- **The simulator disagrees** (`results/evictblock/test_episodes.csv`). On D1-D3 the same detector:
  - evicts 5,300-6,200 attacker entries per A4 episode and 2,900-6,700 per E9P episode;
  - blocks both attackers under every attack (A2, A4, A6, E9P);
  - never blocks a benign host.
- So this is a **simulator-to-testbed gap in detection**, not a failure seen in development.

**Likely causes (hypotheses, not yet tested):**

1. **Poll jitter.** Under attack the controller is overloaded and the 1 s poll stretches.
   - Interval after the attack start (all defenses): mean 1.2-2.2 s, p95 2.4-8.9 s, maximum 12-30 s.
   - Without attack the poll runs at 1.00 s.
   - Several features count in polls or per poll (`idle_polls`, `active_ratio`, `log_dpkts`,
     `gap_*`), so they shift away from the simulator's exact 1 s polls. A mimicry attack, whose
     only tell is its timing regularity, then looks benign.
2. **Threshold.** The testbed τ (T1, 0.639) is much higher than D1-D3's (0.19-0.28). It was
   calibrated on simulated bigFlows benign traffic, which scores high, so the margin for
   attack entries that look benign is small.
3. The testbed logs no per-entry scores or features, so these hypotheses cannot be checked from
   the existing runs. Checking them needs a feature and score log (next steps).

## Finding 2: the block rule degenerates when few hosts are flagged, and blocks busy benign hosts

- **The rule** (`loftbench/defenses.py`, `EvictBlock.on_poll`): block a host if its evictions in
  10 s are ≥ 50 and ≥ 3 × the median over hosts.
  - The median is taken over every host that has held an entry (4 benign hosts, 2 attackers, the server).
  - The code divides by `max(median, 1)`.
- **How it degenerates:** when the detector flags few entries, as under A4, or after both
  attackers are already blocked, as in A2 seed 4123, the median is 0. The rule then reduces to
  **"≥ 50 flagged entries in 10 s"**.
- **The effect:** the detector's false positives (30-100 per run, see above) are not spread
  evenly. They cluster on the busiest benign hosts (d1h1 and d1h2 send 3,600-3,900 flows per run)
  and on bursts, so a single benign host can cross 50 in one window.
  - All 5 benign blocks fit this: four under A4 (seeds 4122, 4123, and two in 4124), where the
    attackers were never flagged, and one under A2, 4-12 s after both attackers had been blocked.
  - In the simulator the attackers are always flagged heavily, so the median stays above 0 and
    the outlier test works as intended.

## Finding 3: controller overload affects every defense and dominates the harm users see

| | A2 | A4 | E9P | benign |
|---|---|---|---|---|
| benign first packets lost (every defense, incl. none) | 6-21 % | 15-26 % | 29-48 % | ≤ 0.1 % |
| new-connection probe success after attack start (every defense) | 28-35 % | 27-33 % | 12-13 % | 100 % |

- These losses are many times larger than the differences in `benign_harmed_pct` between
  defenses, which are a few points.
- They come from the single-threaded Ryu controller handling the Packet-In storm. None of the
  defenses fixes this.

## Finding 4: ensguard's own cost adds to the overload

- **Mean decision time per poll under attack:** ensguard 112 / 159 / 270 ms (A2 / A4 / E9P), the
  highest with FTOP and DMS-BTT. The simple defenses take 35-47 ms.
- **Cause:** six tree models (3 RF + 3 CatBoost), scored in Python on about 2,500 entries per
  switch every poll.
- **Effect:** under A4 and E9P, ensguard loses the most benign first packets of all defenses
  (25.6 % and 47.9 %).

## What this means for the paper (option A)

- These are honest results. Report them as the measured gap between simulator and testbed:
  - the detector that generalizes offline and in the simulator, including to the unseen A6,
    loses the mimicry attacks on a real OpenFlow controller under load;
  - the host-block rule needs a floor on its median.
- The same-data detection benchmark (E11) is unaffected. It tests the detector on the
  simulator's data.

## Possible fixes (future work, each needing a new preregistration and fresh seeds)

1. **Block rule:** compare against `max(median, m_0)` with a fixed floor, or require the host's
   flagged fraction of its own entries to be high. A busy benign host has many entries but a
   small flagged fraction.
2. **Features robust to jitter:** measure timing in seconds rather than polls, and train with
   randomized poll intervals in the simulator.
3. **Cheaper scoring:**
   - score only entries whose counters changed;
   - use the RF alone, or a compiled tree ensemble;
   - cap the scoring time per poll.
4. **Data-plane relief for the controller:** an OpenFlow meter limiting Packet-Ins per access
   port. This would help every defense.
5. **Instrument first:** log per-entry scores and features on the testbed in one development
   run, to test hypotheses 1-2 of finding 1 before changing anything.
