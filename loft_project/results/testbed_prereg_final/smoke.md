# Smoke runs (seed 4183): load, act, log

testbed/campaign_smoke.sh; not results. Acts: the defense deleted entries or blocked a host or source. Errors: Traceback lines in the controller log.

| Run | Summary | Errors | seconds | packet_in | deletes | hosts_blocked_attack | hosts_blocked_benign | sources_blocked_attack | sources_blocked_benign | drop_rules | ingress_drops | first_attack_block_s | benign_harmed_pct | benign_deleted_per_min | probe_post_success_pct | attack_share_avg_pct_s11 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| smk_T1B_A2_dms-btt-pool_s4183 | yes | 0 | 310 | 109635 | 17522 | - | - | - | - | 0 | - | - | 0.02 | 15.87 | 19.46 | 20.3 |
| smk_T1B_A2_dms-btt_s4183 | yes | 0 | 312 | 137668 | 26978 | - | - | - | - | 0 | - | - | 0.51 | 3.08 | 32.88 | 23.31 |
| smk_T1B_A2_fever-ll-local_s4183 | yes | 0 | 311 | 80623 | 1707 | 2 | 0 | - | - | 6 | 2 | 72.6 | 0.03 | 1.35 | 100.0 | 6.22 |
| smk_T1B_A2_fever-ll-novol_s4183 | yes | 0 | 311 | 78405 | 1706 | 2 | 0 | - | - | 6 | 2 | 73.2 | 0.03 | 1.16 | 100.0 | 6.21 |
| smk_T1B_A2_fever-noml_s4183 | yes | 0 | 311 | 97263 | 4730 | 2 | 0 | - | - | 7 | 2 | 111.7 | 0.0 | 0.0 | 81.92 | 14.78 |
| smk_T1B_A2_flora-pool_s4183 | yes | 0 | 353 | 108468 | 7561 | - | - | 2 | 2 | 0 | - | - | 2.69 | 31.27 | 58.77 | 15.56 |
| smk_T1B_A2_flora_s4183 | yes | 0 | 336 | 106129 | 3156 | - | - | 2 | 0 | 0 | - | - | 0.1 | 5.89 | 66.73 | 16.46 |
| smk_T1B_A2_ftmaster-pool_s4183 | yes | 0 | 346 | 127064 | 3854 | - | - | 2 | 0 | 0 | - | - | 0.14 | 8.15 | 28.32 | 8.57 |
| smk_T1B_A2_ftodefender-pool_s4183 | yes | 0 | 311 | 76483 | 2072 | - | - | 2 | 1 | 0 | - | - | 2.79 | 230.55 | 100.0 | 0.02 |
| smk_T1B_A2_ftodefender_s4183 | yes | 0 | 311 | 73106 | 819 | - | - | 2 | 0 | 0 | - | - | 0.25 | 17.94 | 100.0 | 0.02 |
| smk_T1B_A2_ftop-pool_s4183 | yes | 0 | 457 | 123346 | 53378 | - | - | - | - | 0 | - | - | 2.35 | 1151.29 | 31.94 | 30.25 |
| smk_T1B_E9P_ftop-pool_s4183 | yes | 0 | 313 | 93193 | 32528 | - | - | - | - | 0 | - | - | 0.33 | 774.63 | 13.28 | 49.82 |
| smk_T1B_EVX_fever-fl-ll_s4183 | yes | 0 | 310 | 96278 | 0 | - | - | - | - | 0 | - | - | 0.0 | 0.0 | 98.65 | 30.81 |
| smk_UHt_A2_fever-fl-ll_s4183 | yes | 0 | 313 | 15047 | 2300 | 2 | 0 | - | - | 8 | 2 | 98.8 | 0.0 | 0.0 | 99.61 | 11.15 |
