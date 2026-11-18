# FEVER project: state and handoff (18 November 2026, 01:40)

For an assistant picking up this work. Read this first, then the files it names.

## 1. The project

FEVER defends SDN switches against low-rate flow table overflow (LOFT) attacks.
- **Detector:** lossless (histogram-based) federated XGBoost, 300 trees, depth 6, trained across
  three controllers C1-C3 (each on its own traffic and two attacks); only per-bin gradient/hessian sums
  are exchanged (XGBoost collective, `fl/run_fedxgb_hist.py`). Threshold tau = 0.4953 on T1B, set at
  0.1 % false alarms on C3's benign T1A validation runs. Config: `results/v21/exported/ens_config_fl_ll.json`.
- **Response (EvictBlock, `loftbench/defenses.py`; fixed since 9 Nov, do not propose new mechanisms):**
  above occupancy rho = 70 %, evict entries scoring >= tau; block a host if within 10 s it had >= 50
  evictions, >= 20 % of its entries evicted and >= 3x the median host's evictions (median floored at 10);
  volume rule at >= 90 % occupancy: host holds > X (1.5x the busiest benign host in calibration; T1B
  s11/s12/s13 = 799.5/784.5/796.5) and >= 3x the median host. Blocks are permanent, installed as a
  drop rule for the host's MAC at its access-switch ingress.
- **Target venue:** IEEE NetSoft 2027 (2025/2026 full papers: 9 pages including references).
- Repository: `~/LOFT_ATTACK_MITIGATION/loft_project`, branch `loft-v2`, remote origin.

## 2. Standing rules (the user's)

- Never handle passwords or sudo. The user runs
  `sudo bash ~/LOFT_ATTACK_MITIGATION/loft_project/testbed/root/install.sh` (needed after any change
  under testbed/ that the installed snapshot /opt/loft-testbed uses, including the wrapper
  testbed/root/loft-testbed). Never reinstall while a run is going.
- Testbed only through `sudo -n loft-testbed` (passwordless; /usr/local/sbin/loft-testbed).
- One run at a time, never alongside CPU-heavy jobs. Laptop on AC, lid open, no Chrome or Zoom (the
  campaign scripts wait while chrome or zoom runs). Don't edit running bash scripts. Long jobs with
  `systemd-run --user`. Confirm with the user before long campaigns.
- Every study: preregistration in docs/*_prereg.md, approved by the user and committed before code and
  runs; amendments recorded honestly with date and reason.
- Commit: `git -c user.name=asifahmedutsa -c user.email=asifahmedutsa@gmail.com commit`, message ending
  with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; push with
  `git -c http.postBuffer=524288000 push -q origin loft-v2`.
- Never commit: "Other Paper/", traces, large pkl, fl_data npz, results/v21/exported JSONs
  (dmsB_*_T1B.json show as modified), sim_T1B/, pool_T1B/, docs/fever_architecture.pdf, model JSONs
  under results/tbfl/baselines_tb/, fake outputs.
- After running testbed/fig_final.py, `git checkout --` any fig_*.pdf that changed only in metadata.
- Documents must not look AI-generated: plain journal style, booktabs tables, one-line captions, no
  bold emphasis rows, no em-dashes, no "crucial/leverage/novel/comprehensive". Compare only with
  published methods. Use they/them for the user.
- Report flaws promptly, including your own mistakes.

## 3. Environments and tools

- `~/.venvs/loft/bin/python`: reportlab, pytest, xgboost 3.4.1, pandas (all builders and analyses
  that need packages). `~/.venvs/fl`: federated training. System python3: stdlib only (testbed
  analysis scripts). `/opt/loft-testbed/bin/python38 -m py_compile` to check testbed code.
- LaTeX installed 17 Nov (texlive, no recommends): `make` in paper/ builds main.pdf.
- Run data: `~/loft-runs` is a symlink to `/media/utsa/New Volume/loft_data/loft-runs` (NTFS, mounted
  from /etc/fstab). Windows dual-boots on the same disk (sda3).

## 4. Data recovery (17 Nov)

The run folders vanished from the NTFS listing after unclean boots on 15 Nov; Windows chkdsk put them
in found.000 and they were renamed back by the name in each runner.log
(`loft_data/recovery_2026-11-17.log`, `loft-runs/RECOVERY_NOTE.md`). All 532 final-campaign runs are
back; 525 match results/testbed_prereg_final/runs.csv exactly. **Lost:** the seven runs counted under
amendment 1 (their _failed copies); the folders under those names are uncounted reruns. Do not rerun
testbed/analyze_final.py for the paper (it would use the reruns); fig_final.py stops at fig_timeline
for the same reason (tables are built before that). Backup of all fin_* runs: `~/loft-runs-backup`
(3 GB, MD5SUMS verified).

## 5. Experiments: what is done (commit, result)

| Study | Prereg | Results | Outcome |
|---|---|---|---|
| Final campaign, 532 runs, T1B and UHt, 7 attacks, 6 baselines | docs/final_campaign_prereg.md (56f1669) | results/testbed_prereg_final (c804521; amendment 3 e388fb4) | 25 of 33 tests supported; H2 fails vs FTODefender, H5 on T1B (Slow, EVX) fails, H6 fails |
| Flash crowds, round 1 | docs/flash_prereg.md | results/testbed_flash (406e3a2) | F1, F2 pass, but **flawed**: Ryu could not take the Packet-Ins; OVS dropped 18-29 % of controller messages (rconn_overflow), s11 never passed 79 %, volume rule never exercised |
| More attackers (4, 8), G2 and EVX, 54 runs | docs/scale_prereg.md (5195573) | results/testbed_scale (71b59d7) | S1 supported vs FTMaster, DMS-BTT, not FTODefender; S3 pass; FEVER caught 32/36 EVX attackers by the eviction rule |
| Secure aggregation + federated threshold | docs/secagg_plan.md (181d57e) | results/secagg (4088e93) | Masked = unmasked bit for bit; +2.1 % time; false alarms 0.79 -> 0.69 % (still above 0.1 %). User asked to leave it out of the results PDF |
| Flash crowds, round 2 | docs/flash2_prereg.md (27489b6) | results/testbed_flash2 (43e2218) | spread: pass; one host: FEVER blocked the crowd host in 2 of 3 runs (fail) |
| Crowd guard | docs/crowdguard_prereg.md (71dc82f) | results/crowd_signal (fb403b1) | gate G0 failed; study stopped, nothing built |
| Sensitivity of FEVER's settings (rho 0.6/0.8, k 2/4, X at 1.25/2.0 times), 90 runs | docs/sensitivity_prereg.md (58eddf1) | results/testbed_sens (e5299f9) | R1 17 of 18 pass (rho 0.8 on Mimic fails: 15.0 vs 4.9 % occupancy); R2 pass; R3: every setting blocked the one-host crowd host in 3 of 3 runs |

Headline numbers (T1B): FEVER harm 0.011 % vs 1.0-5.2 %; new-connection success 84.2 % vs 21-46 %;
occupancy 6.8 % vs 24-36 %; Mimic/Aware 4.9/14.1 % vs 33-49 %; federated recall on attacks seen only
elsewhere 75.8 -> 90.5 %, Mimic 0.2 -> 61 %; decision 20.8 ms, CPU 62 %, memory 253 MB.

## 6. Flash crowds, round 2 (done) and the crowd guard (stopped)

- Round 2 (docs/flash2_prereg.md 27489b6; results/testbed_flash2, 43e2218): tables of 2,000 entries,
  crowds at F2 (selection: s11 1,885 entries, 0 % controller messages dropped), seeds 4187-4189,
  48 runs, none invalid. **Spread:** FEVER passes F1, F2 (no benign host blocked, harm 0.020 %).
  **One host (d1h3):** FEVER fails both: blocked d1h3 in seeds 4187 (eviction rule, table 87 %) and
  4189 (volume rule, table 91 %); harm 4.89 % vs 0 %. No other method blocked a host. In report.md
  "benign hosts blocked" counts each block twice (host block + ingress drop); runs.csv
  hosts_blocked_benign counts once.
- Crowd guard (docs/crowdguard_prereg.md, fixed 71dc82f): idea = block only hosts whose flows are
  refreshed (seen again 2-10 s after the previous packet). **Gate G0 failed** (fb403b1,
  results/crowd_signal/report.md): crowd host share <= 0.17 (pass) but attackers 0.50-0.67 in the first
  3-14 s of the check (fill phase) and Pulse 0.00 at each on period. Per the preregistration the study
  stopped; no FEVER variant was built and the thresholds must not be changed. Any new attempt needs a
  new, separate preregistration and the user's approval.
- Write-ups updated with round 2: results PDF Section 6.6 / Table 4 / summary, findings summary
  finding 6, paper (Flash crowds paragraph, Discussion, Conclusion; the wrong "traffic generator"
  sentence is gone).

## 7. Documents

- **docs/fever_experiments_results.pdf** (docs/build_results_section.py): paper-style setup and results,
  shortened to 5 pages at the user's request; no limitations, no future work, no secure aggregation;
  Section 6.8 and Table 6 on the sensitivity study; summary of findings in ten short plain items; 6 pages.
- **docs/fever_findings_summary.pdf** (docs/build_findings_summary.py): two pages, ten findings in
  plain words with their numbers (finding 8: settings).
- **docs/fever_observations.pdf** (docs/build_observations.py): older supervisor summary of the final
  campaign (16 Nov), unchanged.
- **paper/** (NetSoft draft, IEEEtran): main.tex, refs.bib (details from the PDFs in
  "Other Paper/M Sc Paper"), tables/ (`make sync` copies them from results/testbed_prereg_final/paper
  in a smaller font), figs/make_architecture.py (architecture figure of the tested design),
  main.pdf 8 pages, no overfull boxes; Results has a subsection and Table VIII (tables/sens.tex, hand-written) on the sensitivity study. Still open in the paper: author block placeholder; FEVER has no
  name expansion. The federated model is not identical to pooled XGBoost (sketch merge; F1 86.8 vs
  86.5) and must not be called identical.

## 8. Facts that are easy to get wrong

- FTODefender's mean harm on T1B is 3.4 % (new-connection success 45.6 %), not 1.0 %.
- No defense has the lowest decision time (19.4 ms); FEVER is lowest among defenses (20.8 ms).
- `rconn_overflow` counts messages dropped instead of queued: drop share = overflow / (queued + overflow).
- Truth files' t_first is the scheduled send time, not the actual one.
- The controller's per-poll counters (packet_in, installs) are cumulative; use differences.
- `pgrep -f <pattern>` from a shell whose command line contains the pattern matches itself.
- In the one-host crowd, round 2's FEVER run on seed 4188 filled s11 more slowly (1,601 entries in the first crowd, every other method and setting 1,730 or more), which is likely why it was not blocked there (exploratory).
- Run names: sens_ (sensitivity), fin_<trace>_<attack>_<method>_s<seed> (campaign), sc<n>_ (more attackers), fc_ / flsel_
  (flash round 1), fc2_ / fl2sel_ (flash round 2). FEVER's method name is fever-fl-ll; DMS-BTT as
  compared is dms-btt-h1.
