"""Send real packets for a simulator schedule from inside a Mininet host.

The host builds the simulator's whole episode (loftbench.traffic.build_traffic, the same
random streams, packets after --duration dropped) and the simulator's dedicated-port
assignment (loftbench.ports), then sends the flows of its own access port: benign host i
sends port i (benign flows hashed by client address, or by the trace anchor for replayed
traces T1-T3), attacker j sends port 4 + j. Both modes write the 5-tuples they emit
(ground truth) to --truth. Run as root inside the host namespace:

  python3 traffic_driver.py --mode benign --domain D1 --seed 4000 --share 0/4 \
      --iface h1-eth0 --dst 10.1.0.100 --duration 300 --truth h1_truth.csv
  python3 traffic_driver.py --mode attack --domain D1 --variant A2 --seed 4000 \
      --attacker 0 --iface h5-eth0 --dst 10.1.0.100 --start 50 --duration 300 --truth h5_truth.csv
Lab use only, inside an isolated emulated network.
"""
import argparse
import csv
import os
import socket
import struct
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from loftbench.config import attack_variant  # noqa: E402
from loftbench.data import profile_of  # noqa: E402
from loftbench.ports import assign_ports  # noqa: E402
from loftbench.traffic import build_traffic  # noqa: E402


def int2ip(x):
    return socket.inet_ntoa(struct.pack("!I", int(x) & 0xFFFFFFFF))


def checksum(b):
    if len(b) % 2:
        b += b"\0"
    s = sum(struct.unpack("!%dH" % (len(b) // 2), b))
    s = (s >> 16) + (s & 0xFFFF)
    s += s >> 16
    return (~s) & 0xFFFF


def frame(src_mac, dst_mac, src, dst, sport, dport, size):
    payload = b"\0" * max(0, size - 42)
    udp = struct.pack("!HHHH", sport, dport, 8 + len(payload), 0) + payload
    iph = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(udp), 0, 0, 64, 17, 0,
                      socket.inet_aton(src), socket.inet_aton(dst))
    iph = iph[:10] + struct.pack("!H", checksum(iph)) + iph[12:]
    return dst_mac + src_mac + b"\x08\x00" + iph + udp


def mac_bytes(m):
    return bytes(int(x, 16) for x in m.split(":"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["benign", "attack"], required=True)
    ap.add_argument("--domain", default="D1")
    ap.add_argument("--variant", default="A2")
    ap.add_argument("--seed", type=int, default=4000)
    ap.add_argument("--share", default="0/4", help="i/4: benign host i sends access port i's flows")
    ap.add_argument("--attacker", type=int, default=0)
    ap.add_argument("--iface", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--dst-mac", default="00:00:00:00:00:64")
    ap.add_argument("--start", type=float, default=50.0)
    ap.add_argument("--duration", type=float, default=300.0)
    ap.add_argument("--truth", required=True)
    a = ap.parse_args()

    prof, didx = profile_of(a.domain)
    if a.mode == "benign":
        # Benign flows do not depend on the attack, so any variant gives the same schedule.
        tr = build_traffic(prof, didx, None, a.seed, a.duration, a.start)
        port = int(a.share.split("/")[0])
    else:
        tr = build_traffic(prof, didx, attack_variant(a.variant), a.seed, a.duration, a.start)
        port = 4 + a.attacker
    tr = assign_ports(tr, "dedicated")
    keep = tr.flow_port[tr.pkt_fid] == port
    t, fid, size, src = tr.pkt_t[keep], tr.pkt_fid[keep].astype(np.int64), tr.pkt_size[keep], tr.flow_src
    order = np.argsort(t, kind="stable")
    t, fid, size = t[order], fid[order], np.clip(size[order], 60, 1500)

    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
    s.bind((a.iface, 0))
    src_mac = s.getsockname()[4]
    dst_mac = mac_bytes(a.dst_mac)
    sport = lambda f: 1024 + (f * 7919) % 60000  # noqa: E731
    dport = lambda f: 1 + (f * 104729) % 1023    # noqa: E731
    seen = set()
    with open(a.truth, "w", newline="") as fh:
        w = csv.writer(fh)
        # t_first: wall-clock time of the flow's first packet (aligns with controller_*_t0.txt).
        w.writerow(["src", "dst", "proto", "sport", "dport", "label", "t_first"])
        t0 = time.time()
        sent = 0
        for tt, f, sz in zip(t, fid, size):
            delay = t0 + tt - time.time()
            if delay > 0:
                time.sleep(delay)
            sip = int2ip(src[f])
            s.send(frame(src_mac, dst_mac, sip, a.dst, sport(int(f)), dport(int(f)), int(sz)))
            sent += 1
            if f not in seen:
                seen.add(f)
                w.writerow([sip, a.dst, 17, sport(int(f)), dport(int(f)), int(a.mode == "attack"),
                            f"{t0 + tt:.3f}"])
    print(f"{a.mode}: sent {sent} packets on {len(seen)} flows; lag {time.time() - t0 - a.duration:.1f}s")


if __name__ == "__main__":
    main()
