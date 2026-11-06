"""Ryu (OpenFlow 1.3) controller for one LOFT domain.

Monitored switch (dpid LOFT_DPID): reactive per-5-tuple rules with idle
timeout, table-full handling, 1 s flow-stats polling, and an optional
defense. Other switches do plain L2 learning. The defenses are the
simulator's own classes (loftbench.defenses: DualGuard, DMSBTT, PortGuard)
and the feature extractor is loftbench.features, so the testbed runs exactly
the code the simulator evaluates.

Environment variables:
  LOFT_DPID         monitored switch datapath id (int, default 1)
  LOFT_ACCESS_DPID  access switch datapath id; its learned MAC-to-port table gives each
                    flow's ingress (access) port for PortGuard (default: none)
  LOFT_DEFENSE      ensguard (FL-EnsGuard: federated RF + CatBoost, evict, block outlier hosts,
                    PortGuard fallback; LOFT_MODEL_DIR/ens_config.json, loftbench.ensjson) |
                    none | dualguard | dms-btt | portguard | dualguard+portguard |
                    dualguard+floodguard | ftmaster | ftop | flora | rdefender | dualguard+hold |
                    dualguard+portguard+hold | dualguard+evict | dualguard+fairevict |
                    dualguard+fairevictq (fair eviction with churn quarantine, knobs from
                    LOFT_MODEL_DIR/fairevictq_selected.json)
  LOFT_MODEL_DIR    directory with v21_<D>.json, dmsB_state_<D>.json, dmsB_flow_<D>.json
                    and defenses.json (see loftbench.export_testbed); for the published
                    baselines also {ftmaster,ftop}_{state,rule}_<D>.json, flora_rule_<D>.json
                    and baselines.json (see loftbench.testbed_baselines)
  LOFT_DOMAIN       domain name for the model files (D1, D2, D3)
  LOFT_MODEL        explicit path to the v2.1 model JSON (overrides LOFT_MODEL_DIR)
  LOFT_LOG          CSV path for the per-second controller log
  LOFT_CAPACITY     flow-table capacity (default 3500)
  LOFT_IDLE         idle timeout seconds (default 10)
  LOFT_LEAN         1 (default) = lean Packet-In handling, 0 = acceptance runs 1-3 behaviour:
                    no repeat install of a flow within 0.5 s, 1 s back-off after TABLE_FULL,
                    and slow-path packets output directly instead of resubmitted to the table
  LOFT_DROP_RULES   1 (default) = enforce PortGuard's quota in the switch: while an access
                    port's quota is full, a drop rule for that port's host (by source MAC,
                    priority DROP_PRIO, hard timeout DROP_S) keeps its new flows from reaching
                    the controller; refreshed at every poll and on every refused Packet-In.
                    0 = refuse in the controller only. The DMS-BTT blocklist and the flow hold
                    are per flow (a drop rule would take the entry it frees, and a per-host
                    rule would block the host's other flows), so they always refuse in the
                    controller.
  LOFT_ENTRYLOG     1 = per monitored switch, record every entry's counters at every poll for
                    offline scoring (testbed/entrylog.py): <switch log>_entries.bin holds one
                    record per poll (float64 t, n, installs since the last poll; then n int32
                    flow ids, int64 packets, int64 bytes, float64 install times), and
                    <switch log>_keys.csv maps each flow id to its 5-tuple, source MAC and port.
                    Default 0 (off).
  LOFT_INSTALL_CLOCK controller (default) = each entry's install time is when the controller
                    sent its flow-mod; switch = poll time minus the entry's duration (the
                    matrix of results_v2.md 18). The poll time is when Ryu processes the
                    stats reply, which lags the switch by a varying queueing delay under load,
                    so with "switch" the install time moves from poll to poll and the feature
                    tracker restarts the history of entries that are not new.
"""
import csv
import json
import os
import sys
import time

import numpy as np
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib import hub
from ryu.lib.packet import ethernet, ipv4, packet, tcp, udp
from ryu.ofproto import ofproto_v1_3

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from loftbench.baselines import FloRa, FTMaster, FTOP, RDefender, SIFT, TableGuard  # noqa: E402
from loftbench.cbjson import CatBoostJSON  # noqa: E402
from loftbench.defenses import DMSBTT, DualGuard, EvictBlock, FloodGuard, PortGuard  # noqa: E402
from loftbench.ensjson import EnsembleJSON  # noqa: E402
from loftbench.fairevictq import QuarantineFairEvict, _parse as feq_parse  # noqa: E402
from loftbench.features import FeatureTracker  # noqa: E402
from loftbench.sim import Defense  # noqa: E402
from loftbench.treejson import TreeJSON  # noqa: E402

MAX_FLOWS = 1 << 20
N_PORTS = 64          # access-port ids learned at run time; OTHER_PORT for unknown sources
OTHER_PORT = N_PORTS - 1
PRIO = 10
DROP_PRIO = 5         # below the per-flow rules, above the non-IP L2 rules and the table miss
DROP_S = 2            # drop-rule hard timeout; refreshed at every 1 s poll while the quota is full
DEFENSES = ("none", "evict", "sift", "tableguard", "dualguard", "dms-btt", "portguard", "dualguard+portguard",
            "dualguard+floodguard", "ftmaster", "ftop", "flora", "rdefender", "dualguard+hold",
            "dualguard+portguard+hold", "dualguard+evict", "dualguard+fairevict",
            "dualguard+portguard+hostid", "portguard+hostid",
            "dualguard+fairevictq", "ensguard", "ensguard-v4lite")


def ip2int(s):
    a, b, c, d = (int(x) for x in s.split("."))
    return (a << 24) | (b << 16) | (c << 8) | d


class ExportedMLP:
    def __init__(self, path):
        m = json.load(open(path))
        self.W = [np.array(w, dtype=np.float32) for w in m["weights"]]
        self.mean = np.array(m["mean"], np.float32)
        self.std = np.array(m["std"], np.float32)
        self.tau = float(m["tau"])
        self.knobs = {k: m[k] for k in ("rho", "t_short", "h_crit", "target") if k in m}
        self.idx = m.get("feature_idx")

    def predict_proba(self, X):
        if self.idx is not None:
            X = X[:, self.idx]
        X = (X - self.mean) / self.std
        h = np.maximum(X @ self.W[0] + self.W[1], 0)
        z = (h @ self.W[2] + self.W[3])[:, 0]
        return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


def build_defense(name, model_dir, domain, model_path=None):
    """The simulator's defense objects, configured from exported files."""
    if name not in DEFENSES:
        raise ValueError(f"LOFT_DEFENSE must be one of {DEFENSES}")
    # +hostid: PortGuard's quota per host (source MAC) instead of per ingress port; the
    # controller handles the identity and port security (LoftController._port).
    name = name[:-len("+hostid")] if name.endswith("+hostid") else name
    if name in ("sift", "tableguard"):
        # Settings selected on validation seeds by gate G1 (loftbench.gate_g1), copied next to
        # the exported models.
        sel = json.load(open(os.path.join(model_dir, "gate_g1_selected.json")))[name]["selected"]
        kw = {k: float(v) for k, v in (x.split("=") for x in sel.split("|")[1].split(","))}
        return (SIFT if name == "sift" else TableGuard)(**kw)
    if name in ("none", "evict"):
        # evict: no defense, Open vSwitch evicts the entry nearest expiry (run_testbed.py).
        d = Defense()
        d.name = name
        return d
    cfg = json.load(open(os.path.join(model_dir, "defenses.json"))) if model_dir else {}
    if name == "dms-btt":
        b = cfg["dms_blocklist"]
        return DMSBTT(CatBoostJSON(os.path.join(model_dir, f"dmsB_state_{domain}.json")),
                      CatBoostJSON(os.path.join(model_dir, f"dmsB_flow_{domain}.json")),
                      h1=b["h1"], h2=b["h2"], p_thresh=b["p_thresh"], numb_mode=b["numb_mode"],
                      blocklist_s=b["blocklist_s"])
    if name in ("ftmaster", "ftop", "flora", "rdefender"):
        # Published baselines (E4/E5), with the knobs and models of the simulator's E2.
        b = json.load(open(os.path.join(model_dir, "baselines.json")))

        def tree(k):
            return TreeJSON(os.path.join(model_dir, f"{k}_{domain}.json"))
        if name == "ftmaster":
            return FTMaster(tree("ftmaster_state"), tree("ftmaster_rule"), **b["ftmaster"])
        if name == "ftop":
            return FTOP(tree("ftop_state"), tree("ftop_rule"), **b["ftop"])
        if name == "flora":
            return FloRa(CatBoostJSON(os.path.join(model_dir, f"flora_rule_{domain}.json")), **b["flora"])
        return RDefender(**b["rdefender"])
    pg = cfg.get("portguard", {})
    if name in ("ensguard", "ensguard-v4lite"):
        # Selected in the simulator (loftbench.evictblock, results/evictblock/selected.json):
        # PortGuard's knobs but mode "full", so detection and blocking run while it enforces.
        # ensguard-v4lite (docs/v4lite_plan.md, results/v4lite): CatBoost only and the floored
        # block rule, from ens_config_v4lite.json.
        cfile = "ens_config.json" if name == "ensguard" else "ens_config_v4lite.json"
        ec = json.load(open(os.path.join(model_dir, cfile)))
        b = ec["block"]
        eb = EvictBlock(EnsembleJSON(model_dir, ec), ec["tau"][domain], name="evictblock",
                        rho=ec["rho"][domain], window_s=b["window_s"], n_min=b["n_min"],
                        f_min=b["k"], block_s=b["block_s"], exempt=(OTHER_PORT,),
                        m0=b.get("m0", 1.0), frac_min=b.get("frac_min", 0.0))
        return PortGuard(eb, name=name, mode="full", **{k: pg[k] for k in pg if k != "mode"})
    if name == "portguard":
        return PortGuard(None, name=name, **{k: pg[k] for k in pg if k != "mode"})
    m = ExportedMLP(model_path or os.path.join(model_dir, f"v21_{domain}.json"))
    k = m.knobs
    h_crit = float(k.get("h_crit", 0.90))
    dg = DualGuard(m, m.tau, name="dualguard", rho=k.get("rho", 0.5), t_short=k.get("t_short", 1.0),
                   hard=h_crit <= 1.0, h_crit=h_crit, target=k.get("target", 0.80))
    if name.endswith("+hold"):
        # Flow hold selected in the simulator (loftbench.flowhold), set before PortGuard
        # reads the admit filter.
        h = cfg["flowhold"]["v2.1+pg" if "portguard" in name else "v2.1"]
        dg.hold_s, dg.strikes, dg.sticky = h["hold_s"], h["strikes"], h["sticky"]
        dg.admit_filter = dg._admit_hold
        name = name[:-len("+hold")]
    if name in ("dualguard", "dualguard+evict", "dualguard+fairevict"):
        # The eviction variants differ only in the switch's overflow policy (run_testbed.py).
        dg.name = name
        return dg
    if name == "dualguard+fairevictq":
        # Switch eviction as +fairevict, plus the quarantine selected in the simulator.
        # results/fairevictq/selected.json, copied next to the exported models (the installed
        # testbed snapshot carries only those).
        sel = json.load(open(os.path.join(model_dir, "fairevictq_selected.json")))["selected"]
        theta, r_min, hold = feq_parse(sel)
        return QuarantineFairEvict(dg, theta=theta, r_min=r_min, hold_s=hold, name=name)
    if name == "dualguard+floodguard":
        fg = json.load(open(os.path.join(model_dir, "baselines.json")))["floodguard"]
        return FloodGuard(dg, name=name, **fg)
    return PortGuard(dg, name=name, **pg)


class Switch:
    """Per-switch state: flows, features, the defense and its drop rules, counters, log."""

    def __init__(self, ctl, dpid, log_path):
        self.dpid, self.name, self.dp = dpid, f"s{dpid:x}", None
        self.defense = build_defense(ctl.defense_name, os.environ.get("LOFT_MODEL_DIR"),
                                     os.environ.get("LOFT_DOMAIN", "D1"), os.environ.get("LOFT_MODEL"))
        self.del_pending, self.idle_of, self.prev, self.prev_t = set(), {}, {}, 0.0
        self.fid_of, self.key_of, self.src_of = {}, [], np.zeros(MAX_FLOWS, np.int64)
        self.port_of = np.full(MAX_FLOWS, OTHER_PORT, np.int16)
        self.tracker = FeatureTracker(MAX_FLOWS, self.src_of, ctl.capacity, 1.0)
        self.install_t = np.zeros(MAX_FLOWS)
        self.defense.reset({"cfg": None, "n_flows": MAX_FLOWS, "flow_src": self.src_of,
                            "flow_port": self.port_of, "n_ports": N_PORTS})
        self.admit = getattr(self.defense, "admit_filter", None)
        self.pg = self.defense if isinstance(self.defense, PortGuard) else None
        # ensguard: the evict-block layer inside PortGuard; its blocked hosts get drop rules.
        self.eb = self.pg.inner if self.pg is not None and isinstance(self.pg.inner, EvictBlock) else None
        self._blocks_logged = 0
        # Churn quarantine: a quarantined host's entries go with one delete matching its MAC,
        # and a drop rule keeps its new flows from the controller (as PortGuard's quota).
        self.feq = self.defense if isinstance(self.defense, QuarantineFairEvict) else None
        self.drop_rules = os.environ.get("LOFT_DROP_RULES", "1") == "1" and (
            self.pg is not None or self.feq is not None)
        self.drop_until, self.drop_pk, self.ref_mac = {}, {}, {}
        self.last_install, self.refused_until = {}, {}
        self._installs_seen = self._tf_last = 0
        self._parts = []
        self.cnt = dict(packet_in=0, table_full=0, installs=0, deletes=0, demotes=0, blocked=0,
                        drop_rules=0, drop_rule_full=0, port_deletes=0)
        self.log = open(log_path, "w", newline="")
        self.w = csv.writer(self.log)
        self.w.writerow(LOG_COLS)
        # Entries per source MAC at each poll, for the papers' attack share of the table.
        self.maclog = open(log_path.replace(".csv", "_macs.csv"), "w", newline="")
        self.mw = csv.writer(self.maclog)
        self.mw.writerow(["t", "mac", "entries"])
        self.elog = self.klog = None
        if os.environ.get("LOFT_ENTRYLOG", "0") == "1":
            self.elog = open(log_path.replace(".csv", "_entries.bin"), "wb")
            self.klog = open(log_path.replace(".csv", "_keys.csv"), "w", newline="")
            self.kw = csv.writer(self.klog)
            self.kw.writerow(["fid", "src", "dst", "proto", "sport", "dport", "mac", "port"])
            self._keys_logged = 0


LOG_COLS = ["t", "entries", "packet_in", "table_full", "installs", "deletes", "demotes",
            "decision_ms", "event_backlog", "blocked", "drop_rules", "fresh"]


class LoftController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.dpid = int(os.environ.get("LOFT_DPID", "1"))
        acc = os.environ.get("LOFT_ACCESS_DPID")
        self.access_dpid = int(acc) if acc else None
        self.capacity = int(os.environ.get("LOFT_CAPACITY", "3500"))
        self.idle = int(os.environ.get("LOFT_IDLE", "10"))
        self.defense_name = os.environ.get("LOFT_DEFENSE", "none")
        self.mac_to_port = {}
        # Fair eviction groups the switch's entries by source MAC, so they must match on it.
        self.match_mac = self.defense_name in ("dualguard+fairevict", "dualguard+fairevictq")
        self.mac_of = {}
        # Switch eviction (overflow_policy=evict): Open vSwitch does not report evictions to an
        # OpenFlow 1.3 controller, so the 1 s polls infer them (_evictions).
        self.evict_mode = "evict" in self.defense_name
        self.install_clock = os.environ.get("LOFT_INSTALL_CLOCK", "controller")
        self.xid_key, self.drop_xids = {}, set()
        self.lean = os.environ.get("LOFT_LEAN", "1") == "1"
        # Host identity (+hostid, tree only): a flow's "port" for PortGuard is its source host,
        # and access switches pin each host port to the first MAC seen on it (port security),
        # so a host cannot rotate MACs to get more quotas.
        self.hostid = self.defense_name.endswith("+hostid") or self.defense_name.startswith("ensguard")
        self.host_of, self.port_mac = {}, {}
        self.t0 = time.time()
        log = os.environ.get("LOFT_LOG", "loft_controller_log.csv")
        # Wall-clock origin of the log's t column, to align it with the traffic drivers.
        with open(log.replace(".csv", "_t0.txt"), "w") as f:
            f.write(f"{self.t0:.6f}\n")
        # Tree topology (run_testbed --topo tree3): several monitored switches, each with its
        # own defense; LOFT_TOPO maps {dpid: {port: [neighbour dpid, its port]}}. The per-second
        # domain log then sums the switches' counters at each poll of the core (LOFT_DPID), and
        # each switch also logs on its own. A flow's port is the switch's own ingress port.
        dpids = os.environ.get("LOFT_DPIDS")
        self.tree = bool(dpids)
        self.topo = {int(d): {int(q): v for q, v in m.items()}
                     for d, m in json.loads(os.environ.get("LOFT_TOPO", "{}")).items()}
        self.sw = {}
        for d in ([int(x) for x in dpids.split(",")] if self.tree else [self.dpid]):
            path = log if not self.tree else log.replace("controller_", "switch_").replace(
                ".csv", f"_s{d:x}.csv")
            self.sw[d] = Switch(self, d, path)
        if self.tree:
            self.log = open(log, "w", newline="")
            self.w = csv.writer(self.log)
            self.w.writerow(LOG_COLS)
        self.flowlog = open(log.replace(".csv", "_flows.csv"), "w", newline="")
        self.fw = csv.writer(self.flowlog)
        self.fw.writerow(["t", "event", "src", "dst", "proto", "sport", "dport", "sw"])
        hub.spawn(self._monitor)

    # ------------------------------------------------------------------
    def _send_flow(self, dp, match, actions, idle, cmd=None, priority=PRIO):
        p, o = dp.ofproto_parser, dp.ofproto
        inst = [p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, actions)]
        msg = p.OFPFlowMod(datapath=dp, priority=priority, match=match,
                           instructions=inst, idle_timeout=idle,
                           command=o.OFPFC_ADD if cmd is None else cmd,
                           flags=o.OFPFF_SEND_FLOW_REM)
        dp.send_msg(msg)                      # assigns msg.xid
        return msg

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features(self, ev):
        dp = ev.msg.datapath
        p, o = dp.ofproto_parser, dp.ofproto
        self._send_flow(dp, p.OFPMatch(), [p.OFPActionOutput(o.OFPP_CONTROLLER, o.OFPCML_NO_BUFFER)],
                        0, priority=0)
        if dp.id in self.sw:
            self.sw[dp.id].dp = dp

    def _key(self, ip, l4):
        sp = dp_ = 0
        if isinstance(l4, (tcp.tcp, udp.udp)):
            sp, dp_ = l4.src_port, l4.dst_port
        return (ip.src, ip.dst, ip.proto, sp, dp_)

    def _match(self, p, k):
        src, dst, proto, sp, dpt = k
        f = dict(eth_type=0x0800, ipv4_src=src, ipv4_dst=dst, ip_proto=proto)
        if self.match_mac and k in self.mac_of:
            f["eth_src"] = self.mac_of[k]
        if proto == 6:
            f.update(tcp_src=sp, tcp_dst=dpt)
        elif proto == 17:
            f.update(udp_src=sp, udp_dst=dpt)
        return p.OFPMatch(**f)

    def _access_port(self, mac):
        """Ingress access port of a source MAC, learned on the access switch."""
        if self.access_dpid is None:
            return OTHER_PORT
        port = self.mac_to_port.get(self.access_dpid, {}).get(mac)
        return port if port is not None and 0 <= port < OTHER_PORT else OTHER_PORT

    def _port(self, S, mac, in_port):
        """A flow's port for the defense: the switch's ingress port in the tree, the host's
        access port (learned on the access switch) otherwise."""
        if self.tree and self.hostid:
            return self.host_of.setdefault(mac, min(len(self.host_of) + 1, OTHER_PORT - 1))
        if self.tree:
            return in_port if 0 <= in_port < OTHER_PORT else OTHER_PORT
        return self._access_port(mac)

    def _macs_on(self, S, port):
        """Host MACs behind a port of switch S."""
        if self.tree and self.hostid:
            return [m for m, h in self.host_of.items() if h == port]
        if self.tree:
            return [m for m, q in self.mac_to_port.get(S.dpid, {}).items() if q == port]
        return [m for m, q in self.mac_to_port.get(self.access_dpid, {}).items() if q == port]

    def _downstream(self, dpid, out, dst):
        """The monitored switches after dpid on the way to dst: (switch, in_port, out_port)."""
        hops = []
        while out in self.topo.get(dpid, {}):
            nd, np_ = self.topo[dpid][out]
            nout = self.mac_to_port.get(nd, {}).get(dst)
            if nd not in self.sw or nout is None:
                break
            hops.append((self.sw[nd], np_, nout))
            dpid, out = nd, nout
        return hops

    def _decide(self, S, k, ip, mac, in_port, out, now, t):
        """Admit and install flow k on switch S: installed, skip (in flight) or refused."""
        fid = S.fid_of.get(k)
        if fid is None:
            fid = len(S.key_of)
            S.fid_of[k] = fid
            S.key_of.append(k)
            S.src_of[fid] = ip2int(ip.src)
            S.port_of[fid] = self._port(S, mac, in_port)
        if self.lean and (now - S.last_install.get(k, -1e9) < 0.5
                          or now < S.refused_until.get(k, 0.0)):
            # Install already in flight, or refused moments ago: forward this packet
            # on the slow path without another flow-mod.
            return "skip"
        dp = S.dp
        p = dp.ofproto_parser
        if S.admit is not None and not S.admit(np.array([fid]), t)[0]:
            # Refused by the defense (DMS-BTT blocklist, PortGuard quota): drop, as in
            # the simulator.
            S.cnt["blocked"] += 1
            self.fw.writerow([round(t, 3), "blocked", *k, S.name])
            # Only a PortGuard quota refusal blocks the whole host; a per-flow refusal (the
            # flow hold of a demoted flow) stays in the controller, like DMS-BTT's blocklist.
            held = getattr(S.pg.inner, "held_until", None) if S.pg is not None else None
            if (S.drop_rules and S.port_of[fid] != OTHER_PORT
                    and (held is None or held[fid] <= t)):
                S.ref_mac.setdefault(int(S.port_of[fid]), {})[mac] = now
                self._drop_rule(S, mac, now)
            return "refused"
        idle = int(round(float(S.defense.admit_timeouts(np.array([fid]), t, self.idle)[0])))
        fm = self._send_flow(dp, self._match(p, k), [p.OFPActionOutput(out)], max(idle, 1))
        self.xid_key[(S.dpid, fm.xid)] = k        # attribute a TABLE_FULL error to its flow
        S.last_install[k] = now
        S.install_t[fid] = round(t, 3)
        S.idle_of[fid] = max(idle, 1)
        S.cnt["installs"] += 1
        self.fw.writerow([round(t, 3), "install", *k, S.name])
        return "installed"

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        msg = ev.msg
        dp = msg.datapath
        p, o = dp.ofproto_parser, dp.ofproto
        in_port = msg.match["in_port"]
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None:
            return
        if self.hostid and in_port not in self.topo.get(dp.id, {}) and dp.id != self.dpid:
            # Port security on an access switch's host port: one MAC per port.
            owner = self.port_mac.setdefault((dp.id, in_port), eth.src)
            if owner != eth.src:
                S0 = self.sw.get(dp.id)
                if S0 is not None:
                    S0.cnt["spoof_drops"] = S0.cnt.get("spoof_drops", 0) + 1
                return
        self.mac_to_port.setdefault(dp.id, {})[eth.src] = in_port
        out = self.mac_to_port[dp.id].get(eth.dst, o.OFPP_FLOOD)
        actions = [p.OFPActionOutput(out)]
        ip = pkt.get_protocol(ipv4.ipv4)
        S = self.sw.get(dp.id)
        if S is not None:
            S.cnt["packet_in"] += 1
        if ip is not None and S is not None and S.dp is not None and out != o.OFPP_FLOOD:
            k = self._key(ip, pkt.get_protocol(tcp.tcp) or pkt.get_protocol(udp.udp))
            self.mac_of.setdefault(k, eth.src)
            now = time.time()
            t = now - self.t0
            # In the tree the flow is also installed on the monitored switches further along
            # its path, each asking its own defense, so it costs one Packet-In. A switch that
            # refuses stops the walk; the packet is then dropped there.
            hops = [(S, in_port, out)] + self._downstream(dp.id, out, eth.dst)
            for i, (H, hin, hout) in enumerate(hops):
                r = self._decide(H, k, ip, eth.src, hin, hout, now, t)
                if i == 0 and r == "refused":
                    return
                if i == 0 and r == "installed":
                    # Packet-Out through the table so the triggering packet is counted.
                    actions = [p.OFPActionOutput(o.OFPP_TABLE)]
                if r == "refused":
                    break
        elif out != o.OFPP_FLOOD and S is None:
            # Access switches: plain L2 forwarding for everything.
            self._send_flow(dp, p.OFPMatch(in_port=in_port, eth_dst=eth.dst), actions, 30,
                            priority=1)
        elif out != o.OFPP_FLOOD and ip is None:
            # Monitored switch: L2 rules for non-IP only (e.g. ARP), so every new IPv4
            # flow misses and gets its own per-5-tuple entry.
            self._send_flow(dp, p.OFPMatch(in_port=in_port, eth_dst=eth.dst, eth_type=eth.ethertype),
                            actions, 30, priority=1)
        data = msg.data if msg.buffer_id == o.OFP_NO_BUFFER else None
        dp.send_msg(p.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id, in_port=in_port,
                                   actions=actions, data=data))

    def _drop_rule(self, S, mac, now, refresh=False):
        """Drop the host's new IPv4 flows in switch S for DROP_S seconds.

        A refused flow gets no rule, so without this every later packet of the refused host
        is another Packet-In: against the fast-refresh attacker Open vSwitch then drops
        controller messages and benign flows go uninstalled (results_v2.md 16.8). Installing
        only on a refused Packet-In is not enough, because Packet-Ins wait in the controller's
        queue for about a second under attack; hence the refresh at every poll."""
        if not refresh and now < S.drop_until.get(mac, 0.0):
            return
        S.drop_until[mac] = now + DROP_S
        dp = S.dp
        p, o = dp.ofproto_parser, dp.ofproto
        # OFPFC_ADD of an identical match and priority replaces the rule and resets its timeout.
        msg = p.OFPFlowMod(datapath=dp, priority=DROP_PRIO, match=p.OFPMatch(eth_type=0x0800, eth_src=mac),
                           instructions=[], hard_timeout=DROP_S, command=o.OFPFC_ADD)
        dp.send_msg(msg)
        if len(self.drop_xids) > 4096:       # errors arrive within milliseconds; keep it small
            self.drop_xids.clear()
        self.drop_xids.add((S.dpid, msg.xid))
        S.cnt["drop_rules"] += 1
        self.fw.writerow([round(now - self.t0, 3), "drop_rule", mac, "", "", "", "", S.name])

    @set_ev_cls(ofp_event.EventOFPErrorMsg, MAIN_DISPATCHER)
    def error(self, ev):
        o = ev.msg.datapath.ofproto
        S = self.sw.get(ev.msg.datapath.id)
        if S is None:
            return
        if ev.msg.type == o.OFPET_FLOW_MOD_FAILED and ev.msg.code == o.OFPFMFC_TABLE_FULL:
            x = (S.dpid, ev.msg.xid)
            if x in self.drop_xids:
                # A drop rule did not fit: the refusal stays controller-only this second.
                self.drop_xids.discard(x)
                S.cnt["drop_rule_full"] += 1
                return
            S.cnt["table_full"] += 1
            k = self.xid_key.pop(x, None)
            if k is not None:
                now = time.time()
                self.fw.writerow([round(now - self.t0, 3), "refused", *k, S.name])
                if self.lean:
                    S.refused_until[k] = now + 1.0
                    S.last_install.pop(k, None)

    def _evictions(self, S, t, fids, pk):
        """Log entries the switch evicted since the last poll: gone (or reinstalled) without a
        controller delete while their idle timeout could not yet have expired, counted from
        the last poll at which their packet count grew. Entries idle for most of their timeout
        are not counted, so this undercounts evictions slightly."""
        cur, ev = {}, []
        for f, c in zip(fids.tolist(), pk.tolist()):
            old = S.prev.get(f)
            same = old is not None and old[3] == S.install_t[f]
            cur[f] = (c, t if not same or c > old[0] else old[1], S.idle_of.get(f, self.idle),
                      S.install_t[f])
        for f, (c, last, idle, inst) in S.prev.items():
            if f in cur and cur[f][3] == inst:
                continue
            if f in S.del_pending:
                S.del_pending.discard(f)
                continue
            if t - last < idle - 1.0:
                S.cnt["evictions"] = S.cnt.get("evictions", 0) + 1
                ev.append(f)
                # Logged at the previous poll: the eviction happened after it, so a return of
                # the flow at any time after that is harm.
                self.fw.writerow([round(S.prev_t, 3), "evict", *S.key_of[f], S.name])
        if S.feq is not None and ev:
            S.feq.note_evicted(np.array(ev, np.int64), S.prev_t)
        S.prev, S.prev_t = cur, t

    # ------------------------------------------------------------------
    def _monitor(self):
        while True:
            hub.sleep(1.0)
            for S in self.sw.values():
                if S.dp is not None:
                    p = S.dp.ofproto_parser
                    S.dp.send_msg(p.OFPFlowStatsRequest(S.dp, match=p.OFPMatch(eth_type=0x0800)))

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def stats(self, ev):
        S = self.sw.get(ev.msg.datapath.id)
        if S is None:
            return
        # OVS splits a large flow-stats reply into several parts (about 550 entries
        # each); act only once the last part has arrived.
        S._parts.extend(ev.msg.body)
        if ev.msg.flags & ev.msg.datapath.ofproto.OFPMPF_REPLY_MORE:
            return
        body, S._parts = S._parts, []
        t = time.time() - self.t0
        t_start = time.perf_counter()
        fids, pk, by, inst = [], [], [], []
        for s in body:
            m = s.match
            if S.feq is not None and s.priority == DROP_PRIO and "eth_src" in m:
                # Packets the quarantined host's drop rule matched: its refused requests. The
                # rule is re-added each poll, which may reset its counter.
                c, old = s.packet_count, S.drop_pk.get(m["eth_src"], 0)
                S.drop_pk[m["eth_src"]] = c
                port = (self.mac_to_port.get(S.dpid, {}).get(m["eth_src"], OTHER_PORT) if self.tree
                        else self._access_port(m["eth_src"]))
                S.feq.note_refused(port, c - old if c >= old else c, t)
                continue
            if s.priority != PRIO or "ipv4_src" not in m:
                continue
            proto = m["ip_proto"]
            sp = m.get("tcp_src", m.get("udp_src", 0))
            dpt = m.get("tcp_dst", m.get("udp_dst", 0))
            fid = S.fid_of.get((m["ipv4_src"], m["ipv4_dst"], proto, sp, dpt))
            if fid is None:
                continue
            fids.append(fid)
            pk.append(s.packet_count)
            by.append(s.byte_count)
            inst.append(t - s.duration_sec - s.duration_nsec * 1e-9)
        fids = np.array(fids, np.int64)
        pk, by = np.array(pk, np.int64), np.array(by, np.int64)
        if self.evict_mode:
            self._evictions(S, t, fids, pk)
        if self.install_clock == "switch":
            inst = np.round(np.array(inst, float), 1)
        else:
            inst = S.install_t[fids]
        # Entries the tracker treats as new this poll (history restarted).
        fresh = int((S.tracker.seen_install[fids] != inst).sum())
        if S.elog is not None:
            self._log_entries(S, t, fids, pk, by, inst, S.cnt["installs"] - S._installs_seen)
        X, dms, state = S.tracker.observe(t, fids, pk, by, inst,
                                          S.cnt["installs"] - S._installs_seen)
        S._installs_seen = S.cnt["installs"]
        n = len(fids)
        obs = dict(t=t, fids=fids, count=n, capacity=self.capacity,
                   table_full_last=S.cnt["table_full"] - S._tf_last,
                   pkts=pk, bytes=by, install_t=inst, X=X, dms=dms, state=state)
        S._tf_last = S.cnt["table_full"]
        dels, dems = S.defense.on_poll(t, obs) if n else (None, None)
        qmacs = []
        if S.feq is not None:
            qp = S.feq.q_until > t
            qp[OTHER_PORT] = False
            if qp.any():
                qmacs = [m for q in np.flatnonzero(qp) for m in self._macs_on(S, q)]
                if dels is not None and len(dels):
                    dels = np.asarray(dels, np.int64)
                    gone = qp[S.port_of[dels]]
                    for f in dels[gone]:
                        if self.evict_mode:
                            S.del_pending.add(int(f))
                        S.last_install.pop(S.key_of[f], None)
                        self.fw.writerow([round(t, 3), "delete", *S.key_of[f], S.name])
                        S.cnt["deletes"] += 1
                    dels = dels[~gone]
                for mac in qmacs:
                    self._delete_host(S, mac)
        for arr, kind in ((dems, "demotes"), (dels, "deletes")):
            if arr is not None and len(arr):
                for f in np.unique(np.asarray(arr, np.int64)):
                    self._delete(S, int(f))
                    S.cnt[kind] += 1
        if qmacs:
            now = time.time()
            for mac in qmacs:
                self._drop_rule(S, mac, now, refresh=True)
        if S.eb is not None:
            # Hosts blocked by the evict-block layer: log new blocks, keep their drop rules.
            for tb, q in S.eb.blocks[S._blocks_logged:]:
                for mac in self._macs_on(S, q):
                    self.fw.writerow([round(t, 3), "host_block", mac, "", "", "", "", S.name])
            S._blocks_logged = len(S.eb.blocks)
            if S.drop_rules:
                now = time.time()
                for q in np.flatnonzero(S.eb.blocked_until > t):
                    if q != OTHER_PORT:
                        for mac in self._macs_on(S, int(q)):
                            self._drop_rule(S, mac, now, refresh=True)
        if S.drop_rules and S.pg is not None:
            # Ports whose quota is full refuse every new flow until the next poll. In the tree
            # a port may carry several hosts (the core's ports); only hosts refused there in
            # the last few seconds get the drop rule.
            full = np.flatnonzero(np.isfinite(S.pg.quota) & (S.pg.used >= S.pg.quota))
            if len(full):
                now = time.time()
                for port in full:
                    if port == OTHER_PORT:
                        continue
                    if self.tree:
                        macs = [m for m, tr in S.ref_mac.get(int(port), {}).items()
                                if now - tr < DROP_S + 1]
                    else:
                        macs = self._macs_on(S, port)[:1]
                    for mac in macs:
                        self._drop_rule(S, mac, now, refresh=True)
        ms = 1000 * (time.perf_counter() - t_start)
        c = S.cnt
        # Events waiting in this app's queue: a growing backlog means the controller is
        # the bottleneck (Packet-Ins wait here before Open vSwitch starts dropping them).
        backlog = self.events.qsize() if hasattr(self, "events") else -1
        if n:
            macs, cnt = np.unique([self.mac_of.get(S.key_of[f], "") for f in fids.tolist()],
                                  return_counts=True)
            for m_, c_ in zip(macs.tolist(), cnt.tolist()):
                S.mw.writerow([round(t, 2), m_, c_])
            S.maclog.flush()
        S.w.writerow([round(t, 2), n, c["packet_in"], c["table_full"], c["installs"],
                      c["deletes"], c["demotes"], round(ms, 2), backlog, c["blocked"],
                      c["drop_rules"], fresh])
        S.log.flush()
        if self.tree and S.dpid == self.dpid:
            tot = {k: sum(x.cnt[k] for x in self.sw.values()) for k in c}
            self.w.writerow([round(t, 2), n, tot["packet_in"], tot["table_full"], tot["installs"],
                             tot["deletes"], tot["demotes"], round(ms, 2), backlog, tot["blocked"],
                             tot["drop_rules"], fresh])
            self.log.flush()
        self.flowlog.flush()

    def _log_entries(self, S, t, fids, pk, by, inst, installs):
        """LOFT_ENTRYLOG: this poll's raw counters, exactly as the feature tracker gets them."""
        for f in range(S._keys_logged, len(S.key_of)):
            k = S.key_of[f]
            S.kw.writerow([f, *k, self.mac_of.get(k, ""), int(S.port_of[f])])
        S._keys_logged = len(S.key_of)
        np.array([t, len(fids), installs], np.float64).tofile(S.elog)
        fids.astype(np.int32).tofile(S.elog)
        pk.astype(np.int64).tofile(S.elog)
        by.astype(np.int64).tofile(S.elog)
        np.asarray(inst, np.float64).tofile(S.elog)
        S.elog.flush()
        S.klog.flush()

    def _delete_host(self, S, mac):
        """One delete for all of a host's per-flow entries (and its drop rule, re-added next)."""
        dp = S.dp
        p, o = dp.ofproto_parser, dp.ofproto
        dp.send_msg(p.OFPFlowMod(datapath=dp, command=o.OFPFC_DELETE, match=p.OFPMatch(
            eth_type=0x0800, eth_src=mac), out_port=o.OFPP_ANY, out_group=o.OFPG_ANY))
        S.cnt["port_deletes"] += 1

    def _delete(self, S, fid):
        dp = S.dp
        p, o = dp.ofproto_parser, dp.ofproto
        k = S.key_of[fid]
        S.last_install.pop(k, None)           # a demoted flow may reinstall at once
        if self.evict_mode:
            S.del_pending.add(fid)
        dp.send_msg(p.OFPFlowMod(datapath=dp, command=o.OFPFC_DELETE_STRICT, priority=PRIO,
                                 match=self._match(p, k), out_port=o.OFPP_ANY,
                                 out_group=o.OFPG_ANY))
        self.fw.writerow([round(time.time() - self.t0, 3), "delete", *k, S.name])
