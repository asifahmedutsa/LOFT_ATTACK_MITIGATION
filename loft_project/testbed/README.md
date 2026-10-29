# Mininet/OVS/Ryu emulation testbed

This harness validates the simulator's findings on real Open vSwitch tables. It needs
root to run Mininet. **Status (29 Oct 2026): acceptance run 1 passed** after two
controller fixes (below); runs 2–4 are in progress. Results are recorded in
`docs/results_v2.md` §16.

## Fixes found by the first runs

1. **Layer-2 rules swallowed IP traffic.** ARP learning installed `in_port, eth_dst`
   rules that also matched IPv4, so after the first ping no new flow ever missed on the
   monitored switch (6 installs in a 300 s run). The monitored switch now installs
   layer-2 rules for non-IP traffic only; access switches keep plain layer-2 forwarding.
2. **Multipart flow-stats replies.** OVS splits large flow-stats replies into parts of
   about 550 entries, and the controller treated each part as the whole table (it never
   saw more than 547 entries). It now accumulates parts until the last one
   (`OFPMPF_REPLY_MORE` cleared) before computing features or acting.

Summarise a run with `python3 testbed/summarize_run.py <run_dir> [--attack-start S]`.
Run one testbed at a time: `sudo mn -c` tears down any other running topology.

## Prerequisites (already present on this machine)

- Mininet 2.3.0, Open vSwitch 3.3.x (`systemctl is-active openvswitch-switch`)
- `~/ryu-env` (Python 3.8, Ryu 4.34, NumPy, scapy)
- Exported models:
  - **v2.1 (default):** `python -m loftbench.v21 --out results/v21 --stages export`,
    which writes `results/v21/exported/v21_<D>.json`. Parity with the Python model has
    been checked: max difference 0.
  - **v2:** `--model-prefix fedprox --model-dir results/v2/exported`.

## Acceptance runs (do these first, in order)

From the `loft_project/` directory:

```bash
# 1. Benign-only control: occupancy stays well below 3,500 and there are no TABLE_FULL errors
sudo python3 testbed/run_testbed.py --domains D1 --variant A2 --attack-start 100000 \
    --defense none --out ~/loft-runs/tb_D1_benign

# 2. Attack, no defense: the table reaches the limit, TABLE_FULL errors appear,
#    and ping RTT/loss degrades
sudo python3 testbed/run_testbed.py --domains D1 --variant A2 --defense none \
    --out ~/loft-runs/tb_D1_A2_none

# 3. Attack with FL-DualGuard
sudo python3 testbed/run_testbed.py --domains D1 --variant A2 --defense dualguard \
    --out ~/loft-runs/tb_D1_A2_dg

# 4. All three domains/controllers simultaneously, unseen variant
sudo python3 testbed/run_testbed.py --domains D1,D2,D3 --variant A6 --defense dualguard \
    --out ~/loft-runs/tb_all_A6_dg
```

Always clean up with `sudo mn -c` afterwards.

Each run writes the following files:

| File | Contents |
|---|---|
| `controller_<D>.csv` | Per-second entries, Packet-In, TABLE_FULL, installs, deletes, demotes, decision ms |
| `controller_<D>_flows.csv` | Install and delete events |
| `truth_*.csv` | Ground-truth 5-tuples |
| `ping_<D>.txt` | Legitimate RTT and loss |
| `final_flows_<D>.txt` | Final flow-table size |

Join the flow events with the truth files to compute benign rejection and eviction,
and the same metrics as the simulator.

## Known caveats to check during the first run

- **Sender throughput.** Python raw-socket senders must sustain ~300 pps per benign
  host and the attack bursts (1,500 pps). The driver prints its lag at exit. If the
  lag exceeds 1 s, reduce `burst_pps` or use more sender processes.
- **Flow-limit setting.** Verify that OVS honors the limit: run
  `ovs-vsctl list Flow_Table`, and confirm that `ovs-ofctl -O OpenFlow13 dump-flows`
  stops growing at about 3,500 entries.
- **Software tables.** Software OVS does not reproduce TCAM timing. Report occupancy
  and admission effects, not line-rate performance.
