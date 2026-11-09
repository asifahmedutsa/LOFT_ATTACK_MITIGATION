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
import json
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
                dpid=int(f"{k:x}1", 16), access_dpid=int(f"{k:x}2", 16), switches=[s1, s2],
                limited=[s1], monitored=None, topo=None)


def build_tree(net, k, dname, port):
    """Three-switch tree (FloRa-style): core s{k}1 to the server, access switches s{k}2 (hosts
    1, 2 and attacker 5) and s{k}3 (hosts 3, 4 and attacker 6). Every table is limited and
    monitored; LOFT_TOPO tells the controller which port leads to which switch."""
    c = net.addController(f"c{k}", controller=RemoteController, ip="127.0.0.1", port=port)
    sw = [net.addSwitch(f"s{k}{j}", dpid=f"{k:x}{j}".zfill(16), protocols="OpenFlow13")
          for j in (1, 2, 3)]
    srv = net.addHost(f"srv{k}", ip=f"10.{k}.0.100/16", mac=f"00:00:00:00:{k:02x}:64")
    net.addLink(srv, sw[0], bw=1000, delay="2ms")
    topo = {}
    for acc in sw[1:]:
        ln = net.addLink(sw[0], acc, bw=250, delay="15ms")
        p0, p1 = sw[0].ports[ln.intf1], acc.ports[ln.intf2]
        topo.setdefault(int(sw[0].dpid, 16), {})[p0] = [int(acc.dpid, 16), p1]
        topo.setdefault(int(acc.dpid, 16), {})[p1] = [int(sw[0].dpid, 16), p0]
    users = []
    for i in range(6):
        h = net.addHost(f"d{k}h{i + 1}", ip=f"10.{k}.1.{i + 1}/16",
                        mac=f"00:00:00:00:{k:02x}:{i + 1:02x}")
        net.addLink(h, sw[1] if i in (0, 1, 4) else sw[2], bw=1000, delay="2ms")
        users.append(h)
    return dict(name=dname, c=c, s1=sw[0], s2=sw[1], srv=srv, users=users, port=port,
                dpid=int(sw[0].dpid, 16), access_dpid=None, switches=sw, limited=sw,
                monitored=[int(x.dpid, 16) for x in sw], topo=topo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domains", default="D1")
    ap.add_argument("--topo", default="dumbbell", choices=["dumbbell", "tree3"],
                    help="dumbbell: monitored switch + access switch (DMS-BTT); tree3: core and "
                         "two access switches, all monitored (build_tree)")
    ap.add_argument("--variant", default="A2", help="A1-A7, X<gap>, E9P (adaptive), EVX (volume-evading), benign (no attack) or F2/F4 (flash "
                         "crowd, no attack)")
    ap.add_argument("--seed", type=int, default=4000)
    ap.add_argument("--defense", default="none",
                    choices=["none", "evict", "sift", "tableguard", "dualguard", "dms-btt", "portguard", "dualguard+portguard",
                             "dualguard+floodguard", "ftmaster", "ftop", "flora", "rdefender",
                             "dualguard+hold", "dualguard+portguard+hold", "dualguard+evict",
                             "dualguard+portguard+hostid", "portguard+hostid",
                             "dualguard+fairevict", "dualguard+fairevictq", "ensguard",
                             "ensguard-v4lite", "ensguard-v5", "ensguard-v5-noml", "ftodefender", "ensguard-v6", "fever", "fever-fl", "fever-fl-bag", "fever-fl-ll", "fever-fl-ll-pg",
                             "fever-fl-ll-noing", "fever-ll-local", "fever-ll-novol", "fever-noml", "ftmaster-pool", "ftop-pool", "ftodefender-pool", "flora-pool",
                             "dms-btt-pool"])
    ap.add_argument("--model-dir", default=os.path.join(ROOT, "results", "v21", "exported"))
    ap.add_argument("--model-prefix", default="v21",
                    help="model file prefix: v21 (federated) or local (this controller only), both in "
                         "results/v21/exported; fedprox in results/v2/exported")
    ap.add_argument("--capacity", type=int, default=3500)
    ap.add_argument("--idle", type=int, default=10, help="idle timeout of the per-flow entries, s")
    ap.add_argument("--duration", type=float, default=300)
    ap.add_argument("--attack-start", type=float, default=50)
    ap.add_argument("--ryu", default=os.path.expanduser("~utsa/ryu-env/bin/ryu-manager"))
    ap.add_argument("--python", default=os.path.expanduser("~utsa/ryu-env/bin/python"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--entry-log", action="store_true",
                    help="record every entry's counters at every poll (LOFT_ENTRYLOG=1)")
    ap.add_argument("--no-diag", action="store_true",
                    help="skip Open vSwitch counters and CPU sampling")
    ap.add_argument("--legacy-controller", action="store_true",
                    help="Packet-In handling of acceptance runs 1-3 (LOFT_LEAN=0)")
    ap.add_argument("--install-clock", default="controller", choices=["controller", "switch"],
                    help="entry install times for the features (LOFT_INSTALL_CLOCK)")
    ap.add_argument("--probe", default="none", choices=["none", "newflow"],
                    help="newflow: a benign host opens a new TCP connection to the server every "
                         "0.5 s (E5 service-level harm; testbed/probe_newflow.py)")
    ap.add_argument("--benign-scale", type=float, default=1.0,
                    help="multiplies every domain's benign new-flow rate (load calibration; the attack "
                         "is unchanged)")
    ap.add_argument("--inactivity-probe", type=int, default=30000,
                    help="OVS inactivity probe to the controller, ms (OVS default 5000: a busy controller "
                         "then misses the echo and the switch disconnects)")
    ap.add_argument("--controller-queue", type=int, default=512,
                    help="Open vSwitch queue to each controller, messages (OVS default 100; 0 = leave)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    setLogLevel("info")
    net = Mininet(switch=OVSSwitch, link=TCLink, controller=None, autoSetMacs=False)
    mk = build_tree if a.topo == "tree3" else build
    doms = [mk(net, k + 1, d, 6653 + k) for k, d in enumerate(a.domains.split(","))]

    ctrl = []
    for dm in doms:
        env = dict(os.environ, LOFT_DPID=str(dm["dpid"]), LOFT_DEFENSE=a.defense,
                   LOFT_MODEL_DIR=a.model_dir,
                   LOFT_DOMAIN=dm["name"],
                   LOFT_CAPACITY=str(a.capacity), LOFT_IDLE=str(a.idle),
                   LOFT_MODEL=os.path.join(a.model_dir, f"{a.model_prefix}_{dm['name']}.json"),
                   LOFT_LOG=os.path.join(a.out, f"controller_{dm['name']}.csv"),
                   LOFT_LEAN="0" if a.legacy_controller else "1",
                   LOFT_INSTALL_CLOCK=a.install_clock,
                   LOFT_ENTRYLOG="1" if a.entry_log else "0",
                   PYTHONPATH=ROOT)
        if dm["access_dpid"] is not None:
            env["LOFT_ACCESS_DPID"] = str(dm["access_dpid"])
        if dm["monitored"]:
            env["LOFT_DPIDS"] = ",".join(str(x) for x in dm["monitored"])
            env["LOFT_TOPO"] = json.dumps(dm["topo"])
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
            for sw in dm["switches"]:
                sw.start([dm["c"]])
            # Hard limit + refuse: no silent eviction in the no-defense baseline. The eviction
            # defenses let Open vSwitch evict instead: +evict the entry nearest expiry (OVS
            # default), +fairevict the same within the source MAC (host) holding most entries,
            # i.e. fair eviction with equal shares (loftbench.fairevict, fe-equal-expiry);
            # +fairevictq adds the controller's churn quarantine (loftbench.fairevictq).
            policy = ["overflow_policy=refuse"]
            if a.defense in ("evict", "dualguard+evict", "dualguard+fairevict", "dualguard+fairevictq"):
                policy = ["overflow_policy=evict"]
            if a.defense in ("dualguard+fairevict", "dualguard+fairevictq"):
                policy.append('groups=["NXM_OF_ETH_SRC[]"]')
            for sw in dm["limited"]:
                subprocess.check_call(
                    ["ovs-vsctl", "--", "--id=@t", "create", "Flow_Table",
                     f"flow_limit={a.capacity}", *policy, "--",
                     "set", "Bridge", sw.name, "flow_tables:0=@t"])
            ctl_opts = ([f"controller_queue_size={a.controller_queue}"] if a.controller_queue else []) + \
                ([f"inactivity_probe={a.inactivity_probe}"] if a.inactivity_probe else [])
            if ctl_opts:
                for sw in (x.name for x in dm["switches"]):
                    for uuid in subprocess.check_output(
                            ["ovs-vsctl", "get", "Bridge", sw, "controller"]).decode().strip("[]\n ").split(","):
                        if uuid.strip():
                            subprocess.check_call(["ovs-vsctl", "set", "Controller", uuid.strip(), *ctl_opts])
        time.sleep(3)
        net.pingAll(timeout="1")
        diag = None
        if not a.no_diag:
            # Where do Packet-Ins go missing? Open vSwitch coverage counters (e.g. rconn_overflow:
            # messages to a controller dropped because its queue was full) before and after the
            # traffic, and per-second CPU of each controller and of ovs-vswitchd.
            subprocess.call(f"ovs-appctl coverage/show > {a.out}/ovs_coverage_before.txt", shell=True)
            pids = [str(c.pid) for c in ctrl] + subprocess.check_output(
                ["pidof", "ovs-vswitchd"]).decode().split()
            diag = subprocess.Popen(f"pidstat -u -h -p {','.join(pids)} 1 > {a.out}/cpu_pidstat.txt",
                                    shell=True)
            # Memory (RSS) of the same processes, every 5 s.
            subprocess.Popen(f"pidstat -r -h -p {','.join(pids)} 5 > {a.out}/mem_pidstat.txt", shell=True)
        if "evict" in a.defense:
            # Exact evictions: an OpenFlow 1.4 monitor connection receives Flow-Removed with
            # reason eviction, which Open vSwitch does not send to the OpenFlow 1.3 controller.
            for dm in doms:
                for sw in dm["limited"]:
                    subprocess.Popen(f"ovs-ofctl -O OpenFlow14 monitor {sw.name} 2>&1 | grep --line-buffered "
                                     f"-i evict > {a.out}/ofmon_evict_{sw.name}.txt", shell=True)
        procs = []
        drv = os.path.join(HERE, "traffic_driver.py")
        probe = os.path.join(HERE, "probe_newflow.py")
        servers = []
        if a.probe == "newflow":
            for dm in doms:
                servers.append(dm["srv"].popen([a.python, probe, "--serve", "--port", "7777"]))
            time.sleep(1)
        for dm in doms:
            dst = dm["srv"].IP()
            dmac = dm["srv"].MAC()
            for i, h in enumerate(dm["users"][:4]):
                procs.append(h.popen(
                    [a.python, drv, "--mode", "benign", "--domain", dm["name"], "--seed", str(a.seed),
                     "--variant", a.variant, "--share", f"{i}/4", "--iface", f"{h.name}-eth0", "--dst", dst,
                     "--dst-mac", dmac, "--duration", str(a.duration), "--benign-scale", str(a.benign_scale),
                     "--truth", os.path.join(a.out, f"truth_{h.name}.csv")]))
            # --variant benign or F2/F4: the attacker hosts stay silent.
            silent = a.variant == "benign" or a.variant.startswith("F")
            for j, h in enumerate(dm["users"][4:] if not silent else []):
                procs.append(h.popen(
                    [a.python, drv, "--mode", "attack", "--domain", dm["name"], "--variant", a.variant,
                     "--seed", str(a.seed), "--attacker", str(j), "--iface", f"{h.name}-eth0",
                     "--dst", dst, "--dst-mac", dmac, "--start", str(a.attack_start),
                     "--duration", str(a.duration), "--benign-scale", str(a.benign_scale),
                     "--truth", os.path.join(a.out, f"truth_{h.name}.csv")]))
            # Legitimate service probe: RTT from a benign host every second.
            procs.append(dm["users"][0].popen(
                f"ping -i 1 -c {int(a.duration)} {dst} > {a.out}/ping_{dm['name']}.txt", shell=True))
            if a.probe == "newflow":
                procs.append(dm["users"][1].popen(
                    [a.python, probe, "--dst", dst, "--port", "7777", "--interval", "0.5",
                     "--duration", str(a.duration),
                     "--out", os.path.join(a.out, f"probe_{dm['name']}.csv")]))
        for p in procs:
            p.wait()
        # A traffic driver that crashed leaves a run that looks valid but carries no traffic
        # (2026-11-04: a smoke run "passed" with none); fail it so the matrix discards it.
        bad = [p.args for p in procs if isinstance(p.args, list) and drv in p.args
               and p.returncode not in (0, None)]
        if bad:
            raise SystemExit(f"[testbed] {len(bad)} traffic process(es) failed, e.g. {bad[0]}")
        for p in servers:
            p.terminate()
        if diag is not None:
            diag.terminate()
            subprocess.call("pkill -f '^pidstat -u -h -p'", shell=True)
            subprocess.call("pkill -f '^pidstat -r -h -p'", shell=True)
            for cmd, f in (("ovs-appctl coverage/show", "ovs_coverage_after.txt"),
                           ("ovs-appctl upcall/show", "ovs_upcall.txt"),
                           ("ovs-vsctl list controller", "ovs_controllers.txt")):
                subprocess.call(f"{cmd} > {a.out}/{f}", shell=True)
            for dm in doms:
                for sw in dm["limited"]:
                    sfx = "" if sw is dm["s1"] else f"_{sw.name}"
                    subprocess.call(f"ovs-ofctl -O OpenFlow13 dump-tables {sw.name} | head -8 "
                                    f"> {a.out}/ovs_tables_{dm['name']}{sfx}.txt", shell=True)
        for dm in doms:
            subprocess.call(f"ovs-ofctl -O OpenFlow13 dump-flows {dm['s1'].name} | wc -l "
                            f"> {a.out}/final_flows_{dm['name']}.txt", shell=True)
    finally:
        subprocess.call("pkill -f 'ovs-ofctl -O OpenFlow14 monitor'", shell=True)
        net.stop()
        for c in ctrl:
            c.terminate()
    print(f"[testbed] artifacts in {a.out}")


if __name__ == "__main__":
    main()
