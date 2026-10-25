# Mininet/OVS/Ryu emulation testbed

This harness validates the simulator's findings on real Open vSwitch tables. It needs
root to run Mininet. **Status: written and syntax-checked, but not yet executed**,
because the development session had no sudo. Running it is the main remaining step
before submission.

## Prerequisites (already present on this machine)

- Mininet 2.3.0, Open vSwitch 3.3.x (`systemctl is-active openvswitch-switch`)
- `~/ryu-env` (Python 3.8, Ryu 4.34, NumPy, scapy)
- Exported models: `python -m loftbench.experiment --out results/v2 --stages export`

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
