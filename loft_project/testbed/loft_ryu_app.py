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
  LOFT_DEFENSE      none | dualguard | dms-btt | portguard | dualguard+portguard
  LOFT_MODEL_DIR    directory with v21_<D>.json, dmsB_state_<D>.json, dmsB_flow_<D>.json
                    and defenses.json (see loftbench.export_testbed)
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
                    0 = refuse in the controller only. The DMS-BTT blocklist is per flow (a
                    drop rule would take the entry it frees), so it always refuses in the
                    controller.
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
from loftbench.cbjson import CatBoostJSON  # noqa: E402
from loftbench.defenses import DMSBTT, DualGuard, PortGuard  # noqa: E402
from loftbench.features import FeatureTracker  # noqa: E402
from loftbench.sim import Defense  # noqa: E402

MAX_FLOWS = 1 << 20
N_PORTS = 64          # access-port ids learned at run time; OTHER_PORT for unknown sources
OTHER_PORT = N_PORTS - 1
PRIO = 10
DROP_PRIO = 5         # below the per-flow rules, above the non-IP L2 rules and the table miss
DROP_S = 2            # drop-rule hard timeout; refreshed at every 1 s poll while the quota is full
DEFENSES = ("none", "dualguard", "dms-btt", "portguard", "dualguard+portguard")


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
    if name == "none":
        return Defense()
    cfg = json.load(open(os.path.join(model_dir, "defenses.json"))) if model_dir else {}
    if name == "dms-btt":
        b = cfg["dms_blocklist"]
        return DMSBTT(CatBoostJSON(os.path.join(model_dir, f"dmsB_state_{domain}.json")),
                      CatBoostJSON(os.path.join(model_dir, f"dmsB_flow_{domain}.json")),
                      h1=b["h1"], h2=b["h2"], p_thresh=b["p_thresh"], numb_mode=b["numb_mode"],
                      blocklist_s=b["blocklist_s"])
    pg = cfg.get("portguard", {})
    if name == "portguard":
        return PortGuard(None, name=name, **{k: pg[k] for k in pg if k != "mode"})
    m = ExportedMLP(model_path or os.path.join(model_dir, f"v21_{domain}.json"))
    k = m.knobs
    h_crit = float(k.get("h_crit", 0.90))
    dg = DualGuard(m, m.tau, name="dualguard", rho=k.get("rho", 0.5), t_short=k.get("t_short", 1.0),
                   hard=h_crit <= 1.0, h_crit=h_crit, target=k.get("target", 0.80))
    if name == "dualguard":
        return dg
    return PortGuard(dg, name=name, **pg)


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
        self.defense = build_defense(self.defense_name, os.environ.get("LOFT_MODEL_DIR"),
                                     os.environ.get("LOFT_DOMAIN", "D1"),
                                     os.environ.get("LOFT_MODEL"))
        self.mac_to_port = {}
        self.fid_of, self.key_of, self.src_of = {}, [], np.zeros(MAX_FLOWS, np.int64)
        self.port_of = np.full(MAX_FLOWS, OTHER_PORT, np.int16)
        self.tracker = FeatureTracker(MAX_FLOWS, self.src_of, self.capacity, 1.0)
        self.install_clock = os.environ.get("LOFT_INSTALL_CLOCK", "controller")
        self.install_t = np.zeros(MAX_FLOWS)
        self.defense.reset({"cfg": None, "n_flows": MAX_FLOWS, "flow_src": self.src_of,
                            "flow_port": self.port_of, "n_ports": N_PORTS})
        self.admit = getattr(self.defense, "admit_filter", None)
        self._parts = []
        self.xid_key = {}
        self.lean = os.environ.get("LOFT_LEAN", "1") == "1"
        self.pg = self.defense if isinstance(self.defense, PortGuard) else None
        self.drop_rules = os.environ.get("LOFT_DROP_RULES", "1") == "1" and self.pg is not None
        self.drop_until, self.drop_xids = {}, set()
        self.last_install, self.refused_until = {}, {}
        self._installs_seen = 0
        self._tf_last = 0
        self.dp = None
        self.t0 = time.time()
        self.cnt = dict(packet_in=0, table_full=0, installs=0, deletes=0, demotes=0, blocked=0,
                        drop_rules=0, drop_rule_full=0)
        log = os.environ.get("LOFT_LOG", "loft_controller_log.csv")
        # Wall-clock origin of the log's t column, to align it with the traffic drivers.
        with open(log.replace(".csv", "_t0.txt"), "w") as f:
            f.write(f"{self.t0:.6f}\n")
        self.log = open(log, "w", newline="")
        self.w = csv.writer(self.log)
        self.w.writerow(["t", "entries", "packet_in", "table_full", "installs", "deletes",
                         "demotes", "decision_ms", "event_backlog", "blocked", "drop_rules",
                         "fresh"])
        self.flowlog = open(log.replace(".csv", "_flows.csv"), "w", newline="")
        self.fw = csv.writer(self.flowlog)
        self.fw.writerow(["t", "event", "src", "dst", "proto", "sport", "dport"])
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
        if dp.id == self.dpid:
            self.dp = dp

    def _key(self, ip, l4):
        sp = dp_ = 0
        if isinstance(l4, (tcp.tcp, udp.udp)):
            sp, dp_ = l4.src_port, l4.dst_port
        return (ip.src, ip.dst, ip.proto, sp, dp_)

    def _match(self, p, k):
        src, dst, proto, sp, dpt = k
        f = dict(eth_type=0x0800, ipv4_src=src, ipv4_dst=dst, ip_proto=proto)
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
        self.mac_to_port.setdefault(dp.id, {})[eth.src] = in_port
        out = self.mac_to_port[dp.id].get(eth.dst, o.OFPP_FLOOD)
        actions = [p.OFPActionOutput(out)]
        ip = pkt.get_protocol(ipv4.ipv4)
        if dp.id == self.dpid:
            self.cnt["packet_in"] += 1
        if ip is not None and dp.id == self.dpid and out != o.OFPP_FLOOD:
            k = self._key(ip, pkt.get_protocol(tcp.tcp) or pkt.get_protocol(udp.udp))
            fid = self.fid_of.get(k)
            if fid is None:
                fid = len(self.key_of)
                self.fid_of[k] = fid
                self.key_of.append(k)
                self.src_of[fid] = ip2int(ip.src)
                self.port_of[fid] = self._access_port(eth.src)
            now = time.time()
            t = now - self.t0
            if self.lean and (now - self.last_install.get(k, -1e9) < 0.5
                              or now < self.refused_until.get(k, 0.0)):
                # Install already in flight, or refused moments ago: forward this packet
                # on the slow path without another flow-mod.
                pass
            elif self.admit is not None and not self.admit(np.array([fid]), t)[0]:
                # Refused by the defense (DMS-BTT blocklist, PortGuard quota): drop, as in
                # the simulator.
                self.cnt["blocked"] += 1
                self.fw.writerow([round(t, 3), "blocked", *k])
                if self.drop_rules and self.port_of[fid] != OTHER_PORT:
                    self._drop_rule(dp, eth.src, now)
                return
            else:
                idle = int(round(float(self.defense.admit_timeouts(np.array([fid]), t, self.idle)[0])))
                fm = self._send_flow(dp, self._match(p, k), actions, max(idle, 1))
                self.xid_key[fm.xid] = k          # attribute a TABLE_FULL error to its flow
                self.last_install[k] = now
                self.install_t[fid] = round(t, 3)
                self.cnt["installs"] += 1
                self.fw.writerow([round(t, 3), "install", *k])
                # Packet-Out through the table so the triggering packet is counted.
                actions = [p.OFPActionOutput(o.OFPP_TABLE)]
        elif out != o.OFPP_FLOOD and dp.id != self.dpid:
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

    def _drop_rule(self, dp, mac, now, refresh=False):
        """Drop the host's new IPv4 flows in the switch for DROP_S seconds.

        A refused flow gets no rule, so without this every later packet of the refused host
        is another Packet-In: against the fast-refresh attacker Open vSwitch then drops
        controller messages and benign flows go uninstalled (results_v2.md 16.8). Installing
        only on a refused Packet-In is not enough, because Packet-Ins wait in the controller's
        queue for about a second under attack; hence the refresh at every poll."""
        if not refresh and now < self.drop_until.get(mac, 0.0):
            return
        self.drop_until[mac] = now + DROP_S
        p, o = dp.ofproto_parser, dp.ofproto
        # OFPFC_ADD of an identical match and priority replaces the rule and resets its timeout.
        msg = p.OFPFlowMod(datapath=dp, priority=DROP_PRIO, match=p.OFPMatch(eth_type=0x0800, eth_src=mac),
                           instructions=[], hard_timeout=DROP_S, command=o.OFPFC_ADD)
        dp.send_msg(msg)
        if len(self.drop_xids) > 4096:       # errors arrive within milliseconds; keep it small
            self.drop_xids.clear()
        self.drop_xids.add(msg.xid)
        self.cnt["drop_rules"] += 1
        self.fw.writerow([round(now - self.t0, 3), "drop_rule", mac, "", "", "", ""])

    @set_ev_cls(ofp_event.EventOFPErrorMsg, MAIN_DISPATCHER)
    def error(self, ev):
        o = ev.msg.datapath.ofproto
        if ev.msg.type == o.OFPET_FLOW_MOD_FAILED and ev.msg.code == o.OFPFMFC_TABLE_FULL:
            if ev.msg.xid in self.drop_xids:
                # A drop rule did not fit: the refusal stays controller-only this second.
                self.drop_xids.discard(ev.msg.xid)
                self.cnt["drop_rule_full"] += 1
                return
            self.cnt["table_full"] += 1
            k = self.xid_key.pop(ev.msg.xid, None)
            if k is not None:
                now = time.time()
                self.fw.writerow([round(now - self.t0, 3), "refused", *k])
                if self.lean:
                    self.refused_until[k] = now + 1.0
                    self.last_install.pop(k, None)

    # ------------------------------------------------------------------
    def _monitor(self):
        while True:
            hub.sleep(1.0)
            if self.dp is not None:
                p = self.dp.ofproto_parser
                self.dp.send_msg(p.OFPFlowStatsRequest(self.dp, match=p.OFPMatch(eth_type=0x0800)))

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def stats(self, ev):
        # OVS splits a large flow-stats reply into several parts (about 550 entries
        # each); act only once the last part has arrived.
        self._parts.extend(ev.msg.body)
        if ev.msg.flags & ev.msg.datapath.ofproto.OFPMPF_REPLY_MORE:
            return
        body, self._parts = self._parts, []
        t = time.time() - self.t0
        t_start = time.perf_counter()
        fids, pk, by, inst = [], [], [], []
        for s in body:
            m = s.match
            if s.priority != PRIO or "ipv4_src" not in m:
                continue
            proto = m["ip_proto"]
            sp = m.get("tcp_src", m.get("udp_src", 0))
            dpt = m.get("tcp_dst", m.get("udp_dst", 0))
            fid = self.fid_of.get((m["ipv4_src"], m["ipv4_dst"], proto, sp, dpt))
            if fid is None:
                continue
            fids.append(fid)
            pk.append(s.packet_count)
            by.append(s.byte_count)
            inst.append(t - s.duration_sec - s.duration_nsec * 1e-9)
        fids = np.array(fids, np.int64)
        pk, by = np.array(pk, np.int64), np.array(by, np.int64)
        if self.install_clock == "switch":
            inst = np.round(np.array(inst, float), 1)
        else:
            inst = self.install_t[fids]
        # Entries the tracker treats as new this poll (history restarted).
        fresh = int((self.tracker.seen_install[fids] != inst).sum())
        X, dms, state = self.tracker.observe(t, fids, pk, by, inst,
                                             self.cnt["installs"] - self._installs_seen)
        self._installs_seen = self.cnt["installs"]
        n = len(fids)
        obs = dict(t=t, fids=fids, count=n, capacity=self.capacity,
                   table_full_last=self.cnt["table_full"] - self._tf_last,
                   pkts=pk, bytes=by, install_t=inst, X=X, dms=dms, state=state)
        self._tf_last = self.cnt["table_full"]
        dels, dems = self.defense.on_poll(t, obs) if n else (None, None)
        for arr, kind in ((dems, "demotes"), (dels, "deletes")):
            if arr is not None and len(arr):
                for f in np.unique(np.asarray(arr, np.int64)):
                    self._delete(int(f))
                    self.cnt[kind] += 1
        if self.drop_rules:
            # Ports whose quota is full refuse every new flow until the next poll.
            full = np.flatnonzero(np.isfinite(self.pg.quota) & (self.pg.used >= self.pg.quota))
            if len(full):
                macs = {port: mac for mac, port in self.mac_to_port.get(self.access_dpid, {}).items()}
                now = time.time()
                for port in full:
                    if port != OTHER_PORT and port in macs:
                        self._drop_rule(self.dp, macs[port], now, refresh=True)
        ms = 1000 * (time.perf_counter() - t_start)
        c = self.cnt
        # Events waiting in this app's queue: a growing backlog means the controller is
        # the bottleneck (Packet-Ins wait here before Open vSwitch starts dropping them).
        backlog = self.events.qsize() if hasattr(self, "events") else -1
        self.w.writerow([round(t, 2), n, c["packet_in"], c["table_full"], c["installs"],
                         c["deletes"], c["demotes"], round(ms, 2), backlog, c["blocked"],
                         c["drop_rules"], fresh])
        self.log.flush()
        self.flowlog.flush()

    def _delete(self, fid):
        dp = self.dp
        p, o = dp.ofproto_parser, dp.ofproto
        k = self.key_of[fid]
        self.last_install.pop(k, None)        # a demoted flow may reinstall at once
        dp.send_msg(p.OFPFlowMod(datapath=dp, command=o.OFPFC_DELETE_STRICT, priority=PRIO,
                                 match=self._match(p, k), out_port=o.OFPP_ANY,
                                 out_group=o.OFPG_ANY))
        self.fw.writerow([round(time.time() - self.t0, 3), "delete", *k])
