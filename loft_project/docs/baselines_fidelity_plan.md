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
Not yet corrected.
