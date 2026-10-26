# Submission revision plan

Prepared 26 October 2026 in response to the independent review in `results_v2.md` §9
(commit `4c3cbb2`).

Every quantitative claim in the review was recomputed from
`results/v21/test_episodes.csv` and `results/review/*.csv` and holds:

- **Overflow:** median 3.9 s, p90 8.8 s, maximum 27.7 s; 41.4 % of episodes exceed 5 s.
- **A4:** 12.5 s overflow and 22.1 % malicious occupancy.
- **Clustered significance:** 30/30 cluster wins, p = 1.9e-9.
- **Harm:** only 44 / 55 / 49 % of acted-on benign flows were still active.
- **Adaptive attacker:** every defense reaches 75–85 % impact.
- **`Numb`:** computed from bytes (`features.py:98`).

The review is correct. The current results support a *conditional* claim: the defense
works against LFTO attackers slower than t_short. They do not support the general
claims in the abstract. A strong venue will reject the paper as it stands, mainly for
review items 1, 2, 4 and 5.

Items are grouped by what a reviewer would do without them. **P0** means likely
rejection, **P1** likely major revision, and **P2** polish. "Compute" estimates assume
this 4-core machine.

---

## P0 — must fix before submitting anywhere competitive

### P0-1. Make the defense survive the adaptive attacker (review item 1)

**Problem.** Soft demotion only works if the attacker refreshes more slowly than
t_short = 1 s. An attacker refreshing every 0.8–0.95 s (3.8k–7.5k pps, about 2 Mb/s)
fills the table under every defense. Against fast-mimic, v2 does *worse* than no
defense (85.2 % vs 79.6 %). A reviewer will construct this attack within minutes.

**What to change.** This needs a new design element, not just a threat-model
sentence. Ending the paper with "our defense fails against a slightly faster attacker"
is unpublishable at a good venue.

**Mechanism options.** Choose on validation data only:

- **(a) Per-source / per-prefix Packet-In budget for demoted flows.** Once a flow is
  demoted, its reinstall requests count against a token bucket for its source /24
  (or ingress port). Over budget, it is not reinstalled and is served by the slow
  path or dropped.
  - Benign false positives reinstall rarely; a fast-refresh attacker exhausts its
    budget.
  - Spoofing (A5/A6) defeats per-source buckets, so add a global demoted-reinstall
    budget as a fallback.
- **(b) Escalating timeout.** Each successive demotion of the same 5-tuple halves its
  residency: first t_short = 1 s, then no reinstall for k seconds.
  - Fast refreshers then produce many Packet-Ins, which is itself a detectable signal.
  - Faster attacker refresh means more controller load, so pair this with (a).
- **(c) Reinstall rate as a feature.** A flow demoted N times within a window is
  almost certainly malicious; delete it without reinstalling.
  - This moves the attacker's cost from table occupancy to controller load. Measure
    that load.

**Evidence a reviewer will expect:**

- An **attacker-budget curve**: refresh gap ∈ {0.25, 0.5, 0.8, 1, 2, 5, 9} s, against
  malicious occupancy, benign impact and controller Packet-In rate, for every defense.
  This is the central figure of the revised paper.
- A stated threat-model bound, e.g. "attackers with rate ≤ R pps".
- Proof that the bound is meaningful: at R, a conventional rate detector or link
  monitor would fire.

**Code.** Add variants to `config.py` (the `ADAPTIVE` dict in `probe_adaptive.py` is
a start), the mechanism in `defenses.py`, a sweep script, and tests for the new
reinstall-budget semantics.

**Protocol.** Pre-register the candidate mechanisms and selection rule, as in v2.1.
Select on validation seeds and test once on new seeds (6000–6009).

**Compute:** about 2–3 h.

### P0-2. Replace the harm metric with service-level outcomes (review item 2)

**Problem.** "Benign flows impacted" counts stale entries: only about half of the
acted-on flows ever send again. "Rejected" flows are not dropped; they take the slow
path. No goodput or latency exists anywhere in the evaluation.

**What to change:**

1. **Fix the simulator metric now (cheap).**
   - Count an eviction or demotion as harm only if the flow sends again before it
     would have idled out.
   - Count *extra* Packet-Ins and slow-path packets per benign flow.
   - Report **benign slow-path packet fraction** as the primary simulator metric,
     with flows impacted as secondary.
2. **Add a controller service model.**
   - Packet-In processing capacity μ (e.g. 2–5k msg/s for Ryu; measure it on the
     testbed).
   - Queueing delay for slow-path packets, with drops when the queue overflows.
   - Report **benign packet loss** and **added latency (p50/p99)**.
   - This also makes Packet-In overhead (+24 %) a real cost rather than a footnote.
3. **Testbed (see P0-3).** Measure ping RTT/loss and an iperf/HTTP probe from benign
   hosts. Report goodput loss and latency per defense.

**Wording.** Rename "42.8 % with no defense" to "42.8 % of benign flows refused a
table entry at least once" everywhere until real loss is measured.

**Compute:** simulator changes plus a rerun is about 1.5 h. The testbed portion
belongs to P0-3.

### P0-3. Run the Mininet/OVS testbed (§7.1; review item 8)

**Problem.** Every number is from a custom Python simulator. Security and networking
venues (CNSM, NOMS, NetSoft, ICC, INFOCOM) will not accept a defense paper whose only
evidence is the authors' own simulator. Simulator results are acceptable only *with*
emulation that confirms the trends.

**What to do.**

1. Run acceptance runs 1–4 in `testbed/README.md`. This needs sudo.
2. Then run a reduced matrix on the testbed:
   - Defenses: {none, DMS-BTT, local, v2.1 (or P0-1's v3)}.
   - Variants: {A2, A4, A6, adaptive}.
   - Domains: D1–D3, with at least 3 seeds.
3. Recalibrate τ on testbed benign traffic first (review item 8). Use benign-only
   Mininet runs with separate seeds as the validation set.
4. **Simulator-validity figure:** for no defense and v2.1, overlay simulated and
   emulated occupancy curves for the same schedule. Report agreement (e.g. overflow
   onset time error, occupancy RMSE).
5. **Measure on the testbed:**
   - Real Ryu decision-loop time.
   - Packet-In capacity μ.
   - Benign RTT/loss.
   - OVS flow-mod rate limits.

**Known risks.**

- Python senders may not sustain the schedule; check the lag the drivers print.
- Verify that OVS honors `flow_limit`.
- To reproduce the occupancy fluctuation shown in Fig. 1, add the DELETE batching
  rate.

**DMS-BTT on the testbed.** The `DMSBTT` class has no Ryu port, so the testbed
DMS-BTT baseline is still missing. Add it to `loft_ryu_app.py` (`LOFT_DEFENSE=dms-btt`,
exporting the CatBoost models).

**Effort:** 1–2 days of wall clock, mostly runs.

### P0-4. Make the DMS-BTT comparison fair (review item 4)

**Problem.** DualGuard's knobs were tuned on validation; DMS-BTT's were not. DMS-BTT
also has no memory, and the `Numb` definition is unverified. Reviewers familiar with
DMS-BTT will flag this.

**What to change:**

1. **Get the PDF and check every detail against §4.** Check whether `Numb` is the
   packet count or byte count, along with the CatBoost settings, the
   threshold-trigger semantics, and the elephant rule. Record each deviation in a
   table in the paper's appendix.
2. **Give DMS-BTT the same tuning budget.** Use a grid over H2 ∈ {0.6, 0.7, 0.75,
   0.8}, H1 ∈ {0.85, 0.9, 0.95}, and the flow-classifier threshold ∈ {0.3, 0.5, 0.7}.
   Select on validation with the same rule as DualGuard.
3. **Add "DMS-BTT + blocklist":** deleted malicious 5-tuples are not reinstalled for
   T seconds. This isolates the value of DualGuard's demotion memory from its
   detector.
4. **Add "DMS-BTT + federation":** federate the CatBoost flow model across domains.
   One way is to federate a GBDT via a shared reference set; simpler is to federate
   our MLP over DMS-BTT's three features. This separates "better detector" from
   "better policy".
5. **Report** the A1–A3/A5/A7 subset separately (4.88 % vs 1.97 %, 2.5×) alongside
   A4/A6.

**Compute:** about 1.5 h.

### P0-5. Show federation is necessary, not just attack coverage (review item 5)

**Problem.** Exposure is split 2 + 2 + 2 + 1 by construction, so local models are
guaranteed to miss variants. A reviewer will ask: "Why not share attack *signatures*
or a public labeled attack library instead of running FL?" If a local model trained on
public attack data matches FL, the federated-learning contribution disappears.

**Required comparators:**

1. **Local + shared attack library.** Each domain trains on its own benign traffic,
   plus attack traffic generated from a public set of variants (e.g. A1–A3, the
   published DMS-BTT settings).
2. **Pooled oracle under the v2.1 policy** (missing from §8).
3. **Ensemble of local models** (score averaging, no training rounds). This is a
   cheaper collaboration baseline.

**Where federation genuinely helps.** Benign traffic differs per domain and is
private. Domain-specific benign behavior (D2 IoT periodic flows) is exactly what a
public attack library cannot supply. Design the experiment to test this:
cross-domain benign false-positive rate with shared-library models versus federated
models.

**Make heterogeneity a variable, not a fixed construction:**

- Dirichlet-skewed exposure α ∈ {0.1, 0.5, 1, ∞}.
- 3, 5 and 10 controllers.
- Report the federation gain as a function of α.

**Unseen variant.** Make it genuinely novel, not a recombination of A4 + A5 traits.
Use a leave-one-variant-out protocol over all 7 variants, so "unseen" is averaged
rather than resting on A6 alone.

**Compute:** about 3–4 h (leave-one-out multiplies training runs).

---

## P1 — likely "major revision" if missing

### P1-1. Calibrate the budget per flow, not per entry-poll (review item 6)

- **Problem.** τ bounds the per-(entry, poll) flag rate at 1 %, but a flow is scored
  at every poll while it is installed.
- **Fix.** Calibrate on the per-flow maximum score over its lifetime, or a
  time-to-first-flag survival quantile. Then the budget means "≤ β of benign flows
  are ever acted on".
- **Report** the realized per-flow flag rate on test runs.
- **Decouple from ρ.** The v2.1 benign-only cost of 0.45 % comes from the ρ = 0.7
  gate, not from calibration. Show both.

### P1-2. Report tails, not only means (review item 7)

- **Overflow:** median, p90, maximum, and the share of episodes above 5 s, per
  defense and per variant.
- **Pre-registered limits:** state them as distributional, e.g. "p90 ≤ 10 s", or
  admit they hold on the mean only.
- **A4:** 12.5 s overflow and 22 % occupancy, above the 15 % limit. State this
  failure in the abstract-level summary, not only in an appendix.
- **Confidence intervals:** compute them with a **cluster bootstrap** over (domain,
  seed). The current CIs treat the 210 episodes as independent; they are not. The
  significance conclusion is unchanged (30/30 clusters), but the interval widths will
  change.

### P1-3. Reword the one-shot test claim (review item 3)

- The candidate set came from v2 test-set ablations.
- Replace "pre-registered, one-shot independent confirmation" with: "Design revised
  after an initial test run; configuration then selected on validation under a
  committed rule and evaluated once on fresh seeds."
- For P0-1, the new mechanism should be evaluated on seeds 6000+ **and** on a new
  traffic generator setting (e.g. a different domain profile, D4, held out entirely).
  That supports a stronger "not designed on this data" claim.

### P1-4. Per-domain results (review item 8)

v2.1 impacts 0.58 % (D1), 4.00 % (D2) and 2.13 % (D3) of benign flows. Put the
per-domain table in the main text. Explain D2: IoT periodic flows resemble LFTO, which
is the realistic hard case and worth a paragraph.

### P1-5. Robustness of the ML detector itself (not in the review)

- **Evasion:** A4 mimicry is the only adversarial-feature variant. Add an attacker
  that knows the feature set and shapes per-flow timing and sizes to the benign
  periodic distribution (e.g. jittered gaps, varied sizes, occasional bursts).
- **Federation poisoning:** with 3 clients, one malicious controller is a third of the
  federation. At least discuss it, and ideally show a label-flip client together with
  a robust aggregator (median or trimmed mean).
- **Training-defense shift:** detectors are trained on *undefended* runs and deployed
  on defended tables. This explains the context-feature finding. Either train on
  mixed defended/undefended trajectories, or justify the choice.

### P1-6. Benign traffic realism (not in the review)

- Parametric bigFlows-like traffic will be questioned.
- Replay at least one real trace through the simulator and the testbed:
  bigFlows.pcap (public via tcpreplay), CAIDA, or MAWI. Map trace 5-tuples to flows.
- Report whether the rankings hold.

### P1-7. Related work and novelty positioning

- Cite adaptive/dynamic idle-timeout schemes for flow-table protection, and position
  demotion against them.
- Claim the novelty precisely, as the combination of: federated detection across
  domains, a calibrated action budget, reversible demotion, and (after P0-1) a
  bounded attacker-cost guarantee.
- Include a related-work comparison table: FTMaster, FTOP, FloRa, FTSheild, DMS-BTT,
  FedSec, and ours. Columns: multi-controller, federated, cross-variant
  generalization, reversible action, adaptive attacker, testbed.

---

## P2 — polish

- **Decision time:** report it from the Ryu testbed, not from Python simulator
  timings (review item 8).
- **Communication:** compare against shipping an attack library, and against sharing
  raw labeled samples.
- **Federation as a component:** the earlier FedAvg-vs-FedProx ablation shows no
  benefit from the proximal term. Drop FedProx from the method and keep it as one
  ablation row.
- **Artifact:** pin `requirements.txt`, include a single `make reproduce` target,
  and archive it on Zenodo with a DOI. Venues increasingly award artifact badges.
- **Figures:** Fig. 1 occupancy timelines are noisy at 1 s resolution; smooth them
  (5 s rolling mean) with a raw-trace inset. Add the attacker-budget curve (P0-1)
  and the sim-vs-emulation overlay (P0-3) as the two new headline figures.
- **Legacy material:** remove the legacy `results/*.png` and the old
  `paper_results_section.md` from the repository before the artifact is public.

---

## Suggested order and checkpoints

| Step | Work | Gate before continuing |
|---|---|---|
| 1 ✅ | P0-2 metric fix (sim) + P1-2 tails/cluster CIs + P1-1 per-flow calibration | **Done 26 Oct** (`results_v2.md` §10). Rankings hold: harmed 1.73 % vs 7.92 % for DMS-BTT. The overflow advantage over DMS-BTT is not significant at the cluster level. Per-flow calibration fails the occupancy and overflow limits on validation and is carried into step 4. The controller service model (goodput/latency) is still open. |
| 2 | P0-4 DMS-BTT fairness (needs the PDF) | DMS-BTT tuned/blocklist numbers known |
| 3 | P0-5 comparators + leave-one-variant-out + α sweep | Federation gain survives the shared-library comparator, or the claim is changed |
| 4 | P0-1 adaptive attacker mechanism, pre-registered, fresh seeds 6000+ and held-out D4 | Attacker-budget curve shows a bounded cost |
| 5 | P0-3 testbed (sudo): acceptance, recalibration, reduced matrix, sim-vs-emu figure | Trends reproduce |
| 6 | P1-3..P1-7, P2, paper rewrite | — |

Steps 1–4 are code and compute that can run on this machine; step 5 needs sudo.

**Decision point after step 3.** If a local model with a shared attack library matches
federation, re-scope the paper. It becomes "budget-calibrated reversible mitigation
with a bounded attacker cost", with federation as one deployment option. Such a paper
is still publishable, at NOMS, CNSM or NetSoft.

**Venue fit after the revision:**

- **CNSM, NOMS, NetSoft, IEEE TNSM** fit simulation plus Mininet plus strong
  methodology.
- **INFOCOM or a top security venue** would additionally need a hardware or P4
  testbed and a formal attacker-cost analysis.
