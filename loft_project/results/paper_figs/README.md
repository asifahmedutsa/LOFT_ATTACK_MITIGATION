# Figures in the style of the related papers

Drawn by `testbed/paper_figs.py`. Each PNG has a PDF next to it. The figure types follow
`Other Paper/experiments_summary.md`.

| File | What it shows | Papers that show this figure | Data |
|---|---|---|---|
| fig01_rules_over_time_{A2,A4,E9P} | benign and attack rules in s11 over time, per defense | LOFT, FTMaster, FTODefender, FTOP, FloRa, ALFO, rDefender | v3 testbed, median of 5 seeds |
| fig02_attack_share_over_time | attack-rule share Pa over time, with and without a defense | SFTO-Guard, FTODefender, DMS-BTT | v3 testbed |
| fig03_comparison (+ comparison_table.csv) | avg and max Pa, avg usage, seconds at the limit, Packet-In, Table-Full | FTMaster, FTODefender, FTOP, DMS-BTT, FTShield | v3 testbed, A2/A4/E9P x 5 seeds |
| fig04_packet_in_over_time | controller Packet-In rate: no attack, attack, defended | SFTO-Guard, FTMaster, DMS-BTT, FTShield | v3 testbed |
| fig05_packet_in_loss | benign first packets lost at the controller; benign harm | rDefender | v3 testbed |
| fig06_new_flow_service | success rate and connect time of new connections | LOFT, ALFO | v3 testbed probe |
| fig07_decision_time | processing time per poll | FTMaster, FTOP, SFTO-Guard, rDefender | v3 testbed |
| fig08_cpu_memory | controller CPU and memory | all defense papers | v3 testbed, pidstat |
| fig09_classifier_comparison | Acc / Precision / Recall / F1 by attack exposure | SFTO-Guard, FTMaster, FTOP, FloRa, DMS-BTT, FTShield | E11, simulator D1-D3 |
| fig10_table_composition | attack / benign / free share 150 s into A4 | FTShield | v3 testbed |
| fig11_score_distribution | EnsGuard score, benign vs attack entries | FTODefender | testbed entry logs, seeds 4131-4133 |
| fig12_block_rule_sensitivity | block-rule and tau-budget grid | FTODefender (TH2), FTMaster (threshold) | simulator, development seeds |
| fig13_metrics_by_paper | accuracy, precision, recall and F1, one panel each, all detectors at the same 0.1 % FPR | SFTO-Guard, FTMaster, FTOP, FloRa, DMS-BTT, FTShield | E11, simulator D1-D3 |
| fig14_metrics_by_paper_own_threshold | the same at each paper's own threshold | same | E11 |

`testbed_runs.csv` holds the per-run numbers behind figs 03, 05, 06 and 08.
`scores_ensguard_testbed.npz` is a local cache and is not committed.

Notes:
- Fig. 10 is taken 150 s into the attack, not at 45 s as FTShield does: at 45 s no defense has acted
  yet, and every bar is the same.
- In Fig. 08 every defense runs at about 93 % of one core, because the controller is saturated under
  attack (posthoc_diagnosis.md). CPU therefore does not separate the defenses here.

## v5 campaign (`v5/`)

`PYTHONPATH=. ~/.venvs/loft/bin/python testbed/paper_figs.py --v5` redraws the testbed figures
(01-08, 10) from the preregistered v5 campaign (~/loft-runs/v5_T1B_*, T1B, seeds 4140-4144; none,
EnsGuard v3, v4-lite, v5, DMS-BTT, FTMaster) into `v5/`, with `v5/testbed_runs.csv` and
`v5/comparison_table.csv`, plus two figures of its own:

| File | What | Data |
|---|---|---|
| v5/fig15_per_attack_per_seed | benign harm and attack share per attack; bar = mean, dot = one seed | v5 campaign |
| v5/fig16_a2_block_expiry | A2, seed 4141: s11 entries over time for v5, DMS-BTT and FTMaster; v5's block, its expiry and the time its table was full | v5 campaign (exploratory) |
