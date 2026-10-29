"""Send real packets for a simulator schedule from inside a Mininet host.

Benign mode replays this host's share of the domain's benign flows; attack
mode runs the LFTO recurrence of one attacker. Both write the 5-tuples they
emit (ground truth) to --truth. Run as root inside the host namespace:

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
from loftbench.config import DOMAINS, VARIANTS  # noqa: E402
from loftbench.data import DOMAIN_IDX  # noqa: E402
from loftbench.traffic import _rng, generate_attack, generate_benign  # noqa: E402


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
    ap.add_argument("--share", default="0/1", help="i/n: send flows with fid %% n == i")
    ap.add_argument("--attacker", type=int, default=0)
    ap.add_argument("--iface", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--dst-mac", default="00:00:00:00:00:64")
    ap.add_argument("--start", type=float, default=50.0)
    ap.add_argument("--duration", type=float, default=300.0)
    ap.add_argument("--truth", required=True)
    a = ap.parse_args()

    prof = DOMAINS[a.domain]
    didx = DOMAIN_IDX[a.domain]
    if a.mode == "benign":
        t, fid, size, src, _ = generate_benign(prof, a.duration, didx, _rng("benign", prof.name, a.seed))
        i, n = (int(x) for x in a.share.split("/"))
        keep = fid % n == i
        t, fid, size = t[keep], fid[keep], size[keep]
    else:
        v = VARIANTS[a.variant]
        # Generate the whole attack exactly as the simulator does (same random stream,
        # all attackers), then keep this attacker's flows. Each attacker therefore sends
        # its own source address and 5-tuples, packet for packet as in the simulator.
        owner = []
        t, fid, size, src, _ = generate_attack(v, a.start, a.duration, didx, 0,
                                               _rng("attack", prof.name, v.name, a.seed),
                                               owner_out=owner)
        keep = np.asarray(owner)[fid] == a.attacker
        t, fid, size = t[keep], fid[keep], size[keep]
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
        w.writerow(["src", "dst", "proto", "sport", "dport", "label"])
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
                w.writerow([sip, a.dst, 17, sport(int(f)), dport(int(f)), int(a.mode == "attack")])
    print(f"{a.mode}: sent {sent} packets on {len(seen)} flows; lag {time.time() - t0 - a.duration:.1f}s")


if __name__ == "__main__":
    main()
