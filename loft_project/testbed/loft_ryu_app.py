"""Ryu (OpenFlow 1.3) controller for one LOFT domain.

Monitored switch (dpid LOFT_DPID): reactive per-5-tuple rules with idle
timeout, table-full handling, 1 s flow-stats polling, and an optional
defense (FL-DualGuard policy from an exported model). Other switches do
plain L2 learning. Uses loftbench.features so the testbed and the simulator
share one feature extractor.

Environment variables:
  LOFT_DPID      monitored switch datapath id (int, default 1)
  LOFT_DEFENSE   none | dualguard (default none)
  LOFT_MODEL     path to exported model JSON (dualguard)
  LOFT_LOG       CSV path for the per-second controller log
  LOFT_CAPACITY  flow-table capacity (default 3500)
  LOFT_IDLE      idle timeout seconds (default 10)
  LOFT_LEAN      1 (default) = lean Packet-In handling, 0 = acceptance runs 1-3 behaviour:
                 no repeat install of a flow within 0.5 s, 1 s back-off after TABLE_FULL,
                 and slow-path packets output directly instead of resubmitted to the table
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
from loftbench.features import FeatureTracker  # noqa: E402

MAX_FLOWS = 1 << 20
PRIO = 10


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


class LoftController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.dpid = int(os.environ.get("LOFT_DPID", "1"))
        self.capacity = int(os.environ.get("LOFT_CAPACITY", "3500"))
        self.idle = int(os.environ.get("LOFT_IDLE", "10"))
        self.t_short = 1
        self.defense = os.environ.get("LOFT_DEFENSE", "none")
        self.model = ExportedMLP(os.environ["LOFT_MODEL"]) if self.defense == "dualguard" else None
        self.rho, self.h_crit, self.target = 0.5, 0.90, 0.80
        if self.model is not None:
            k = self.model.knobs
            self.rho = k.get("rho", self.rho)
            self.t_short = int(k.get("t_short", self.t_short))
            self.h_crit = k.get("h_crit", self.h_crit)
            self.target = k.get("target", self.target)
        self.mac_to_port = {}
        self.fid_of, self.key_of, self.src_of = {}, [], np.zeros(MAX_FLOWS, np.int64)
        self.tracker = FeatureTracker(MAX_FLOWS, self.src_of, self.capacity, 1.0)
        self.demoted = set()
        self._parts = []
        self.xid_key = {}
        self.lean = os.environ.get("LOFT_LEAN", "1") == "1"
        self.last_install, self.refused_until = {}, {}
        self._installs_seen = 0
        self.dp = None
        self.t0 = time.time()
        self.cnt = dict(packet_in=0, table_full=0, installs=0, deletes=0, demotes=0)
        log = os.environ.get("LOFT_LOG", "loft_controller_log.csv")
        self.log = open(log, "w", newline="")
        self.w = csv.writer(self.log)
        self.w.writerow(["t", "entries", "packet_in", "table_full", "installs", "deletes",
                         "demotes", "decision_ms", "event_backlog"])
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
            now = time.time()
            if self.lean and (now - self.last_install.get(k, -1e9) < 0.5
                              or now < self.refused_until.get(k, 0.0)):
                # Install already in flight, or refused moments ago: forward this packet
                # on the slow path without another flow-mod.
                pass
            else:
                idle = self.t_short if fid in self.demoted else self.idle
                fm = self._send_flow(dp, self._match(p, k), actions, idle)
                self.xid_key[fm.xid] = k          # attribute a TABLE_FULL error to its flow
                self.last_install[k] = now
                self.cnt["installs"] += 1
                self.fw.writerow([round(now - self.t0, 3), "install", *k])
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

    @set_ev_cls(ofp_event.EventOFPErrorMsg, MAIN_DISPATCHER)
    def error(self, ev):
        o = ev.msg.datapath.ofproto
        if ev.msg.type == o.OFPET_FLOW_MOD_FAILED and ev.msg.code == o.OFPFMFC_TABLE_FULL:
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
        X, _, _ = self.tracker.observe(t, fids, np.array(pk, np.int64), np.array(by, np.int64),
                                       np.round(np.array(inst), 1),
                                       self.cnt["installs"] - self._installs_seen)
        self._installs_seen = self.cnt["installs"]
        n = len(fids)
        if self.model is not None and n and n / self.capacity >= self.rho:
            s = self.model.predict_proba(X)
            flag = s >= self.model.tau
            for f in fids[flag]:
                self.demoted.add(int(f))
                self._delete(int(f))
                self.cnt["demotes"] += 1
            n_after = n - int(flag.sum())
            if n_after / self.capacity >= self.h_crit:
                by_a = np.array(by)
                eleph = by_a >= np.percentile(by_a, 90)
                rest = np.flatnonzero(~flag & ~eleph)
                rest = rest[np.argsort(-s[rest], kind="stable")][:n_after - int(self.target * self.capacity)]
                for f in fids[rest]:
                    self._delete(int(f))
                    self.cnt["deletes"] += 1
        ms = 1000 * (time.perf_counter() - t_start)
        c = self.cnt
        # Events waiting in this app's queue: a growing backlog means the controller is
        # the bottleneck (Packet-Ins wait here before Open vSwitch starts dropping them).
        backlog = self.events.qsize() if hasattr(self, "events") else -1
        self.w.writerow([round(t, 2), n, c["packet_in"], c["table_full"], c["installs"],
                         c["deletes"], c["demotes"], round(ms, 2), backlog])
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
