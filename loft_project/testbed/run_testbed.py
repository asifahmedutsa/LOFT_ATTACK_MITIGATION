"""Multi-controller Mininet/OVS testbed for LFTO experiments (run with sudo).

Per domain k (DMS-BTT reference topology): controller c_k, monitored switch
s{k}1 attached to the server, access switch s{k}2 with six user hosts of
which two are attackers. s{k}1-s{k}2: 250 Mbit/s, 15 ms; host links 1 Gbit/s,
2 ms. The monitored switch's table 0 is limited to --capacity entries with
overflow_policy=refuse so that overflow is observable (not masked by OVS
eviction).

  sudo python3 testbed/run_testbed.py --domains D1 --variant A2 --seed 4000 \
      --defense none --out ~/loft-runs/tb_D1_A2_none
  sudo python3 testbed/run_testbed.py --domains D1,D2,D3 --variant A2 \
      --defense dualguard --model-dir results/v2/exported --out ~/loft-runs/tb_all_dg

Requires Mininet, Open vSwitch and Ryu (default: ~/ryu-env/bin/ryu-manager).
"""
import argparse
import os
import subprocess
import time

from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def build(net, k, dname, port):
    c = net.addController(f"c{k}", controller=RemoteController, ip="127.0.0.1", port=port)
    s1 = net.addSwitch(f"s{k}1", dpid=f"{k:x}1".zfill(16), protocols="OpenFlow13")
    s2 = net.addSwitch(f"s{k}2", dpid=f"{k:x}2".zfill(16), protocols="OpenFlow13")
    srv = net.addHost(f"srv{k}", ip=f"10.{k}.0.100/16", mac=f"00:00:00:00:{k:02x}:64")
    net.addLink(srv, s1, bw=1000, delay="2ms")
    net.addLink(s1, s2, bw=250, delay="15ms")
    users = []
    for i in range(6):
        h = net.addHost(f"d{k}h{i + 1}", ip=f"10.{k}.1.{i + 1}/16",
                        mac=f"00:00:00:00:{k:02x}:{i + 1:02x}")
        net.addLink(h, s2, bw=1000, delay="2ms")
        users.append(h)
    return dict(name=dname, c=c, s1=s1, s2=s2, srv=srv, users=users, port=port,
                dpid=int(f"{k:x}1", 16))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domains", default="D1")
    ap.add_argument("--variant", default="A2")
    ap.add_argument("--seed", type=int, default=4000)
    ap.add_argument("--defense", choices=["none", "dualguard"], default="none")
    ap.add_argument("--model-dir", default=os.path.join(ROOT, "results", "v2", "exported"))
    ap.add_argument("--capacity", type=int, default=3500)
    ap.add_argument("--duration", type=float, default=300)
    ap.add_argument("--attack-start", type=float, default=50)
    ap.add_argument("--ryu", default=os.path.expanduser("~utsa/ryu-env/bin/ryu-manager"))
    ap.add_argument("--python", default=os.path.expanduser("~utsa/ryu-env/bin/python"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    setLogLevel("info")
    net = Mininet(switch=OVSSwitch, link=TCLink, controller=None, autoSetMacs=False)
    doms = [build(net, k + 1, d, 6653 + k) for k, d in enumerate(a.domains.split(","))]

    ctrl = []
    for dm in doms:
        env = dict(os.environ, LOFT_DPID=str(dm["dpid"]), LOFT_DEFENSE=a.defense,
                   LOFT_CAPACITY=str(a.capacity),
                   LOFT_MODEL=os.path.join(a.model_dir, f"fedprox_{dm['name']}.json"),
                   LOFT_LOG=os.path.join(a.out, f"controller_{dm['name']}.csv"),
                   PYTHONPATH=ROOT)
        ctrl.append(subprocess.Popen(
            [a.ryu, "--ofp-tcp-listen-port", str(dm["port"]), os.path.join(HERE, "loft_ryu_app.py")],
            env=env, stdout=open(os.path.join(a.out, f"ryu_{dm['name']}.log"), "w"),
            stderr=subprocess.STDOUT))
    time.sleep(3)
    try:
        net.build()
        for dm in doms:
            dm["c"].start()
        for dm in doms:
            dm["s1"].start([dm["c"]])
            dm["s2"].start([dm["c"]])
            # Hard limit + refuse: no silent eviction in the no-defense baseline.
            br = dm["s1"].name
            subprocess.check_call(
                ["ovs-vsctl", "--", "--id=@t", "create", "Flow_Table",
                 f"flow_limit={a.capacity}", "overflow_policy=refuse", "--",
                 "set", "Bridge", br, "flow_tables:0=@t"])
        time.sleep(3)
        net.pingAll(timeout="1")
        procs = []
        drv = os.path.join(HERE, "traffic_driver.py")
        for dm in doms:
            dst = dm["srv"].IP()
            dmac = dm["srv"].MAC()
            for i, h in enumerate(dm["users"][:4]):
                procs.append(h.popen(
                    [a.python, drv, "--mode", "benign", "--domain", dm["name"], "--seed", str(a.seed),
                     "--share", f"{i}/4", "--iface", f"{h.name}-eth0", "--dst", dst,
                     "--dst-mac", dmac, "--duration", str(a.duration),
                     "--truth", os.path.join(a.out, f"truth_{h.name}.csv")]))
            for j, h in enumerate(dm["users"][4:]):
                procs.append(h.popen(
                    [a.python, drv, "--mode", "attack", "--domain", dm["name"], "--variant", a.variant,
                     "--seed", str(a.seed), "--attacker", str(j), "--iface", f"{h.name}-eth0",
                     "--dst", dst, "--dst-mac", dmac, "--start", str(a.attack_start),
                     "--duration", str(a.duration),
                     "--truth", os.path.join(a.out, f"truth_{h.name}.csv")]))
            # Legitimate service probe: RTT from a benign host every second.
            procs.append(dm["users"][0].popen(
                f"ping -i 1 -c {int(a.duration)} {dst} > {a.out}/ping_{dm['name']}.txt", shell=True))
        for p in procs:
            p.wait()
        for dm in doms:
            subprocess.call(f"ovs-ofctl -O OpenFlow13 dump-flows {dm['s1'].name} | wc -l "
                            f"> {a.out}/final_flows_{dm['name']}.txt", shell=True)
    finally:
        net.stop()
        for c in ctrl:
            c.terminate()
    print(f"[testbed] artifacts in {a.out}")


if __name__ == "__main__":
    main()
