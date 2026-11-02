# Testbed plan: the related papers' experiments on a 3-switch tree

From 2026-11-03 new experiments are the related papers' own experiments
(`Other Paper/experiments_summary.md`, `docs/other_papers_run_plan.md`), run on the Mininet /
Open vSwitch / Ryu testbed. Exception: churn quarantine round 2 (our extension), kept.

## Topology (per controller, one controller per run)

```
            srv (server)
             |
          s{k}1  core       table 3,500, monitored
          /     \\
     s{k}2       s{k}3      access switches, tables 3,500, monitored
    h1 h2 h5    h3 h4 h6    h5, h6 attackers (one per access switch)
```

- Like FloRa's tree (4 switches) and a step up from the DMS-BTT / FTOP dumbbell we used so far
  (today only one switch is limited and monitored).
- Every switch's table is limited and polled; each switch has its own defense instance (same
  models). A new flow's first Packet-In comes from its access switch; the controller asks each
  switch on the path (access, core) and installs where admitted, so a flow costs one Packet-In
  and up to two flow-mods.
- A port is the switch's own ingress port: on an access switch one host, on the core one access
  switch (an attacker and two benign hosts share it, the shared-port case of section 10).
- Benign harm: a benign flow refused or evicted while active at any switch on its path.
- One domain per run: the 4-core laptop already saturates one Ryu controller under attack.
- Old single-switch runs (E5, testbed_fe) stay as they are; the tree runs do not reuse them.

## Experiments (papers in brackets)

| # | Experiment | Runs (300 s, 3 seeds) | Testbed time |
|---|---|---|---|
| T0 | Build and smoke test the tree: 4 runs (none, DualGuard; A2, benign) | 4 | 0.5 h |
| T1 | Main comparison, the papers' table columns (avg/max attack share, table usage, earliest and total overflow, Packet-In, Table-Full) plus harm and the new-connection probe [all]. bigFlows (T1 trace); A1, A2, A3, A4 mimicry, adaptive E9P, benign; defenses none, plain OVS eviction, DMS-BTT, FTMaster, FTOP, rDefender, DualGuard, + PortGuard, + fair eviction | 6 x 9 x 3 = 162 | 19 h |
| T2 | Table size 2K / 3K / 4K [FTMaster, FloRa] and idle timeout 10 / 20 / 30 s [FloRa, rDefender]; A2; none, DMS-BTT, FTMaster, rDefender, DualGuard | 4 x 5 x 3 = 60 | 7 h |
| T3 | Flash crowd: trace replayed at 2x for 12 s windows, no attack and with A2 [FTOP]; same 9 defenses | 2 x 9 x 3 = 54 | 6 h |
| T4 | rDefender's attacks LA, HA, ALA, AHA; ALFO's adaptive attack against eviction [rDefender, ALFO]; 6 defenses | 5 x 6 x 3 = 90 | 10.5 h |
| T5 | Second trace, IMC-10 univ2 [FTOP] (and univ1 [FTMaster, FloRa, rDefender] if fetched): A2, A4, benign; 9 defenses | 3 x 9 x 3 = 81 | 9.5 h |
| T6 | Overhead from T1's logs: controller and switch CPU, memory (RSS), decision time, flow-mods [most papers] | 0 | - |
| Q2 | Churn quarantine round 2 (simulator 40 min, then 9 runs) | 9 | 1 h |

About 53 testbed hours in all; T1 first. Runs go one at a time, nothing else on the laptop
while they run.

## Code work before T0

1. `run_testbed.py --topo tree3`: the tree above, all three tables limited, the switch map
   passed to the controller.
2. `loft_ryu_app.py`: per-switch state (flows, features, defense, logs
   `controller_<dom>_<switch>.csv`), installs along the path.
3. `summarize_run.py` / `collect_e5.py`: per-switch columns, harm over the whole path.
4. Plain OVS eviction as its own defense (`evict`), needed by T1 and T4.
5. Reinstall by you (`sudo bash testbed/root/install.sh`).
