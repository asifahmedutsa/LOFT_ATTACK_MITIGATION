# FEVER project: state and handoff (17 November 2026, 23:45)

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
| **Flash crowds, round 2 (running)** | docs/flash2_prereg.md (27489b6) | results/testbed_flash2 | see section 6 |

Headline numbers (T1B): FEVER harm 0.011 % vs 1.0-5.2 %; new-connection success 84.2 % vs 21-46 %;
occupancy 6.8 % vs 24-36 %; Mimic/Aware 4.9/14.1 % vs 33-49 %; federated recall on attacks seen only
elsewhere 75.8 -> 90.5 %, Mimic 0.2 -> 61 %; decision 20.8 ms, CPU 62 %, memory 253 MB.

## 6. Running now: flash crowds, round 2

- Design (fixed): tables of 2,000 entries (E5_CAP=2000); crowd rate chosen by rule = **F2** (selection
  run reached 1,885 entries with 0 % dropped, results/testbed_flash2/selection.txt); seeds 4187-4189;
  8 methods; two placements: F2 (spread over the 4 benign hosts) and F2H (all crowd flows from d1h3 on
  s13). Pass rules for FEVER per placement: F1 no benign host blocked; F2 mean harm <= no defense + 1.0.
- Code: testbed/traffic_driver.py (F<k>H), testbed/campaign_flash2.sh, testbed/analyze_flash2.py
  (fdcb204); wrapper fix to accept F<k>H (89ba3b6, installed 23:05).
- Progress: all 24 spread runs done (23:02, none failed). The first launch's one-host runs failed with
  "bad --variant" before the wrapper fix (no data affected). Relaunched 23:09 as user service
  `loft-flash2`; at 23:45, 6 of 24 one-host runs done; expected end about 01:30.
- Early look: spread seed 4187 - no benign host blocked by any method, FEVER harm 0.03 %, s11 peak
  1,856. One-host seed 4187 no defense - d1h3 sent all 4,426 crowd flows and held 1,028 entries on
  s11, but s11 peaked at 1,675 (< 1,800), so the volume rule may not be exercised in one-host runs.
  Report as it is; the preregistration does not allow changing k.

**When it finishes:**
1. Check `results/testbed_flash2/campaign.log` (look for FAILED/INVALID; `reruns.md`).
2. `python3 testbed/analyze_flash2.py` -> runs.csv and report.md; check F1/F2 per placement, the drop
   share, s11/s13 peaks and the inferred rule of any d1h3 block.
3. Commit results (not run folders) and push.
4. Update the write-ups: replace round 1's flash-crowd section in docs/build_results_section.py
   (Section 6.6 and Table 4) and in paper/main.tex (Flash crowds paragraph) with round 2, stating that
   round 1's table did not fill because the controller dropped Packet-Ins; update finding 6 in
   docs/build_findings_summary.py. Rebuild the PDFs (~/.venvs/loft/bin/python docs/build_*.py; make
   in paper/).

## 7. Documents

- **docs/fever_experiments_results.pdf** (docs/build_results_section.py): paper-style setup and results,
  shortened to 5 pages at the user's request; no limitations, no future work, no secure aggregation;
  summary of findings in eight short plain sentences (84c7dce).
- **docs/fever_findings_summary.pdf** (docs/build_findings_summary.py): two pages, nine findings in
  plain words with their numbers (9edd1fe).
- **docs/fever_observations.pdf** (docs/build_observations.py): older supervisor summary of the final
  campaign (16 Nov), unchanged.
- **paper/** (NetSoft draft, IEEEtran): main.tex, refs.bib (details from the PDFs in
  "Other Paper/M Sc Paper"), tables/ (`make sync` copies them from results/testbed_prereg_final/paper
  in a smaller font), figs/make_architecture.py (architecture figure of the tested design),
  main.pdf 8 pages, no overfull boxes (63c9d21). Still open in the paper: author block placeholder;
  FEVER has no name expansion; the Limitations paragraph still says the flash crowds failed because
  "the traffic generator could not send faster", which is wrong (fix with round 2); the federated model
  is not identical to pooled XGBoost (sketch merge; F1 86.8 vs 86.5) and must not be called identical.

## 8. Facts that are easy to get wrong

- FTODefender's mean harm on T1B is 3.4 % (new-connection success 45.6 %), not 1.0 %.
- No defense has the lowest decision time (19.4 ms); FEVER is lowest among defenses (20.8 ms).
- `rconn_overflow` counts messages dropped instead of queued: drop share = overflow / (queued + overflow).
- Truth files' t_first is the scheduled send time, not the actual one.
- The controller's per-poll counters (packet_in, installs) are cumulative; use differences.
- `pgrep -f <pattern>` from a shell whose command line contains the pattern matches itself.
- Run names: fin_<trace>_<attack>_<method>_s<seed> (campaign), sc<n>_ (more attackers), fc_ / flsel_
  (flash round 1), fc2_ / fl2sel_ (flash round 2). FEVER's method name is fever-fl-ll; DMS-BTT as
  compared is dms-btt-h1.
