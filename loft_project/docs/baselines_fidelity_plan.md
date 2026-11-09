# Retrained baselines: how the replacement rule of section 4 is applied

*Fixed 9 November 2026, before any retrained model was scored.*

Section 4 of docs/final_campaign_prereg.md: a retrained baseline replaces its simulator-trained model
only if its recall on the standard attacks (G1-G3, Spoof, Pulse) is at least that model's minus 5
points, at false alarms at most 1 %. The baselines have more than one learned model, so the rule is
applied as follows.

**Data.** The T1B test recordings of the testbed (seeds 4176-4178), as FEVER's detector is scored
(results/tbfl/report.md). Nothing here was used to train either model.

**Models.** As the controller runs them: the exported JSON files (earlier: results/v21/exported;
retrained: results/tbfl/baselines_tb/{c3,pool}), at the threshold each defense applies.

| Baseline | Model | Unit | "Attack" means |
|---|---|---|---|
| FTMaster | state (XGBoost) | poll | class 1 |
| FTMaster | rule (XGBoost) | entry | p >= 0.5 |
| FTOP | state (random forest) | poll | class 1 |
| FTOP | rule (random forest) | entry | p >= 0.5 |
| FloRa | rule (CatBoost) | entry | p >= 0.5 |
| DMS-BTT | state (CatBoost, 3 classes) | poll | class 1 or 2 |
| DMS-BTT | flow (CatBoost) | entry | p >= 0.7 (p_thresh) |
| FTODefender | rule (LightGBM-LR) | entry | p >= 0.5 |
| FTODefender | detector (CRITIC score) | poll | DS < th1 (0.65) |

Entry rows: results/tbfl/rows.pkl (5 % of the entries per poll, all three switches). Recall: share of
the attack rows of the five standard attacks' recordings flagged, pooled. False alarms: share of the
rows of the benign-only recordings flagged. Poll rows: every poll of every switch, labelled by the
attack's schedule (loftbench/tbfl_train_baselines.py); recall over the active polls of the five
attacks' recordings, false alarms over all polls of the benign-only recordings. The defenses consult
their state models only above an occupancy level; that gate is not applied here, so poll false alarms
are an upper bound.

**Rule.** Main arm (C3's rows): a baseline's retrained models replace its earlier ones only if every
one of its learned models passes (recall >= earlier recall - 5 points, and false alarms <= 1 %);
otherwise the baseline keeps all its earlier models, so that no baseline mixes training sources.
FTODefender was never exported from the simulator for T1B and its detector has no earlier version: its
retrained models are used, and its numbers are reported. Data-matched arm (C1-C3 pooled): it is
defined by its training rows, so it is not replaced by a simulator model; its numbers are reported,
and a model with false alarms above 1 % is named.

Reported beside the rule, not part of it: recall on Mimic, Slow and Aware, and each attack's recall.
Written by loftbench/tbfl_fidelity.py to results/testbed_baselines_tb/fidelity.md. The comparison with
each paper's headline result (the other half of section 4's fidelity report) is separate.

## Result (9 November 2026)

results/testbed_baselines_tb/fidelity.md. Main arm, by the rule above: FloRa, DMS-BTT and FTODefender
use their C3-retrained models; FTMaster and FTOP keep their simulator models, because their retrained
state models flag 27.7 % and 13.9 % of benign polls (the simulator ones 14.0 % and 0.0 %; FTOP's at
33.5 % recall). The retrained rule models pass everywhere (recall on the standard attacks 99.9 %
against 96.6-97.0 %, false alarms 0.32-0.33 % against 0.10-0.11 %). In the pooled arm every model
is above 1 % false alarms (rule models 1.9-3.7 %, state models 6.4-45.7 %); its rule models detect
Mimic and Slow (78-89 %) where the C3 and simulator models do not (under 0.1 %).

FTODefender's detector flags 90.4 % of benign polls (C3) because of our port, not the method: its
benchmark window is s11's benign flow count (about 980 entries) and the controller applies it to all
three switches, while s12 and s13 hold about 510 and 260 benign entries; their edit distance to the
benchmark is then at its maximum, and the detection score is below th1 at 98-100 % of their benign
polls (s11: 72 % on T1B, 45 % on T1A). The simulator had one switch, so this did not arise there.

**Amendment (9 November 2026, after the result above).** FTODefender's paper protects one switch with
that switch's benchmark, so each switch now has its own: 10 polls from 60 s of the switch in the T1A
benign recording of seed 4173 (s11 968, s12 585, s13 381 entries on average), and CRITIC weights from
that switch's training polls (ftod_config_T1B_<switch>.json; the controller loads the switch's file).
Its other models are unchanged, and the rerun of the scoring reproduced every other row exactly. The
detector then flags 49.4 % of benign polls (C3; pooled 34.0 %), at 95.8 % recall on the standard
attacks (was 90.4 % and 94.2 %). Per switch on a T1B benign recording: s11 68.8 %, s12 29.0 %, s13
52.1 %; on a T1A benign recording other than the benchmark's (seed 4174): 37.0 %, 27.6 %, 13.6 %. What
remains is the method on this traffic, not the port: T1B's benign tables are smaller than T1A's (s11
about 800 against 1,014 entries), and the edit distance matches polls only within eps = 5 % of the
table (175 entries) over a 10-poll window. Kept as is; FTODefender acts on its rule model's flags
(0.32 % of benign entries) whenever the detector fires, so its harm in the campaign shows the cost.

## Deployed (9 November 2026)

results/v21/exported (the main arm, what the controller loads for ftmaster, ftop, flora, dms-btt,
ftodefender): flora_rule, dmsB_state, dmsB_flow (T1B) replaced by the C3-retrained models, the
simulator ones kept in results/v21/exported/sim_T1B/; ftod_rule_T1B and ftod_config_T1B_<switch> added;
FTMaster's and FTOP's T1B files unchanged. results/v21/exported/pool_T1B/: the pooled models, loaded by
the data-matched defenses ftmaster-pool, ftop-pool, ftodefender-pool, flora-pool and dms-btt-pool
(same knobs, baselines.json and defenses.json copied). Checked before installation: each of the ten
defenses builds in the testbed's controller on s11-s13, each loads its own arm's files, and
FTODefender loads each switch's config. FTOP's pooled forest takes 2.3 s to load per switch.

## Against the papers (9 November 2026)

results/testbed_baselines_tb/fidelity_papers.md (loftbench/tbfl_paper_fidelity.py). Detection of the
deployed per-entry models on the T1B test recordings is at or above each paper's published figure:
accuracy 97.6 % (FTMaster, paper 98 % or higher), 97.9 % (FTOP, up to 98 %), 99.8 % (FloRa, 99.49 %;
our false-positive rate 0.26 % against its 0.01 %), 99.9 % (DMS-BTT, above 92 %) and 99.8 %
(FTODefender, 97 %). Mitigation is not yet comparable: the published attack shares (DMS-BTT 5.25 %
on average, FTOP's Pm 20.66 %, FTODefender's 22.23 %) beside our earlier testbed runs on A2 (s11:
DMS-BTT 18.7 %, FTOP 33.9 %, FloRa 39.1 %, FTMaster 10.0 %), which used the simulator models and
controller-only blocks. The campaign's runs give the comparison; a gap that remains is reported with it.
