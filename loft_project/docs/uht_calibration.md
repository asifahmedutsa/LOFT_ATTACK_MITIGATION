# UHt: thresholds recalibrated on the held-out trace's benign recording

*Fixed 9 November 2026, before computing any value below.*

docs/final_campaign_prereg.md, section 5: on UHt, every method whose paper sets a threshold on benign
traffic recalibrates it on the benign recording tbt_UHt_benign_none_s4190 by its own rule; nothing is
retrained. The methods on UHt are none, FTMaster, DMS-BTT, rDefender and FEVER.

| Method | Thresholds | Set on benign traffic by its rule? | On UHt |
|---|---|---|---|
| FTMaster | rule and state models at 0.5, monitoring at 70 % occupancy, block at 0.5 x the table | no, constants of the paper | as on T1B |
| DMS-BTT | h1 0.9, h2 0.6, p_thresh 0.7, blocklist 60 s | no, selected in the simulator (results/revision2/selected.json) | as on T1B |
| rDefender | gamma 0.02, thr_h, thr_l, sizes | no, constants | as on T1B |
| FEVER | tau: 0.1 % of benign rows; volume limit: 1.5 x the busiest benign host per switch | yes | recalibrated |

FTMaster and DMS-BTT run the models they run on T1B (results/v21/exported, the fidelity decision),
copied under the UHt file names the controller loads.

FEVER, by the rules that set its T1B values:
- tau_UHt: the 99.9th percentile of the deployed detector's scores (tb_xgb_ll.json, as the
  controller runs it) on the benign rows of tbt_UHt_benign_none_s4190 (results/tbfl/rows.pkl: 5 %
  of the entries per poll, three switches), as loftbench.models.threshold_at_fpr at 0.001.
- vol_x_UHt per switch: 1.5 x the most entries any host held at that switch in any poll of the
  recording (switch_UHt_<sw>_macs.csv), as loftbench.v5.stage_volume. Checked open loop as there: no
  host of the recording would be blocked.
- rho (0.7) and the block rule are not calibrated values and stay as on T1B.

The recording is at the campaign's UHt load: its per-host flow counts (451, 940, 469, 917) equal
those of build_traffic for UHt at benign scale 1.0 (1,000 pps), seed 4190.

Written to results/v21/exported/ens_config_fl_ll.json (keys "UHt"; the T1B values untouched) by
loftbench/uht_calibrate.py, with results/tbfl/uht_calibration.json.
