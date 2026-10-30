"""Read classic pcap files into per-packet 5-tuple flow records (no dependencies).

    python -m loftbench.pcapflows traces/bigFlows.pcap --out traces/bigflows.npz

Supports microsecond and nanosecond pcap, little or big endian, link types
Ethernet (with 802.1Q tags), raw IPv4 and Linux cooked capture. Keeps IPv4
TCP, UDP and ICMP; everything else (IPv6, ARP, fragments after the first) is
counted and skipped. A flow is one direction of a 5-tuple, which is what a
reactive per-5-tuple OpenFlow controller installs one entry for. Packet sizes
are original wire lengths, so traces with nulled payloads keep their sizes.
"""
import argparse
import glob
import os
import struct

import numpy as np

LINK_ETHERNET, LINK_RAW, LINK_RAW_ALT, LINK_SLL = 1, 101, 12, 113


def _records(path):
    """Yield (timestamp, orig_len, raw_bytes, linktype) for each packet."""
    with open(path, "rb") as f:
        hdr = f.read(24)
        if len(hdr) < 24:
            return
        magic = hdr[:4]
        if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1"):
            end = "<"
        elif magic in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d"):
            end = ">"
        else:
            raise ValueError(f"{path}: not a classic pcap file (pcapng is not supported)")
        nano = magic in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d")
        link = struct.unpack(end + "I", hdr[20:24])[0]
        scale = 1e-9 if nano else 1e-6
        rec = struct.Struct(end + "IIII")
        while True:
            h = f.read(16)
            if len(h) < 16:
                return
            sec, frac, incl, orig = rec.unpack(h)
            data = f.read(incl)
            if len(data) < incl:
                return
            yield sec + frac * scale, orig, data, link


def _ip_offset(data, link):
    if link == LINK_ETHERNET:
        off, etype = 14, data[12:14]
        while etype in (b"\x81\x00", b"\x88\xa8") and len(data) >= off + 4:
            etype, off = data[off + 2:off + 4], off + 4
        return off if etype == b"\x08\x00" else None
    if link in (LINK_RAW, LINK_RAW_ALT):
        return 0 if data[:1] and data[0] >> 4 == 4 else None
    if link == LINK_SLL:
        return 16 if data[14:16] == b"\x08\x00" else None
    raise ValueError(f"unsupported link type {link}")


def read_pcap(paths, max_packets=None):
    """Parse one or more pcap files in order; returns dict of numpy arrays."""
    t, src, dst, sp, dp, proto, size = [], [], [], [], [], [], []
    skipped = 0
    for path in paths:
        for ts, orig, data, link in _records(path):
            o = _ip_offset(data, link)
            if o is None or len(data) < o + 20:
                skipped += 1
                continue
            ihl = (data[o] & 0x0F) * 4
            p = data[o + 9]
            frag = struct.unpack("!H", data[o + 6:o + 8])[0] & 0x1FFF
            s_ip, d_ip = struct.unpack("!II", data[o + 12:o + 20])
            a = b = 0
            if p in (6, 17):
                if frag or len(data) < o + ihl + 4:
                    skipped += 1
                    continue
                a, b = struct.unpack("!HH", data[o + ihl:o + ihl + 4])
            elif p != 1:
                skipped += 1
                continue
            t.append(ts)
            src.append(s_ip)
            dst.append(d_ip)
            sp.append(a)
            dp.append(b)
            proto.append(p)
            size.append(orig)
            if max_packets and len(t) >= max_packets:
                break
        if max_packets and len(t) >= max_packets:
            break
    t = np.asarray(t, np.float64)
    order = np.argsort(t, kind="stable")
    cols = dict(t=t, src=np.asarray(src, np.uint32), dst=np.asarray(dst, np.uint32),
                sport=np.asarray(sp, np.uint16), dport=np.asarray(dp, np.uint16),
                proto=np.asarray(proto, np.uint8), size=np.asarray(size, np.int32))
    cols = {k: v[order] for k, v in cols.items()}
    cols["skipped"] = skipped
    return cols


def to_flows(cols):
    """Group packets into directional 5-tuple flows.

    Returns pkt_t (seconds from the first packet), pkt_fid, pkt_size, and per
    flow: flow_src (source IPv4 as int64), flow_dst, flow_proto."""
    key = np.zeros(len(cols["t"]), dtype=[("s", "u4"), ("d", "u4"), ("a", "u2"), ("b", "u2"),
                                          ("p", "u1")])
    key["s"], key["d"], key["a"], key["b"], key["p"] = (cols["src"], cols["dst"], cols["sport"],
                                                        cols["dport"], cols["proto"])
    _, first, fid = np.unique(key, return_index=True, return_inverse=True)
    # Number flows in order of their first packet.
    rank = np.empty(len(first), np.int64)
    rank[np.argsort(first, kind="stable")] = np.arange(len(first))
    fid = rank[fid.ravel()]
    first_sorted = np.sort(first)
    t = cols["t"] - cols["t"][0] if len(cols["t"]) else cols["t"]
    return dict(pkt_t=t, pkt_fid=fid.astype(np.int64), pkt_size=cols["size"].astype(np.int32),
                flow_src=cols["src"][first_sorted].astype(np.int64),
                flow_dst=cols["dst"][first_sorted].astype(np.int64),
                flow_proto=cols["proto"][first_sorted].astype(np.int8))


def summarize(fl):
    t, fid = fl["pkt_t"], fl["pkt_fid"]
    span = float(t[-1] - t[0]) if len(t) else 0.0
    n_pk = np.bincount(fid)
    return dict(packets=int(len(t)), flows=int(len(n_pk)), span_s=round(span, 1),
                pps=round(len(t) / max(span, 1e-9), 1), flows_per_s=round(len(n_pk) / max(span, 1e-9), 1),
                mean_size=round(float(fl["pkt_size"].mean()), 1),
                single_packet_flows=round(float((n_pk == 1).mean()), 3),
                sources=int(len(np.unique(fl["flow_src"]))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pcaps", nargs="+", help="pcap files or globs, read in sorted order")
    ap.add_argument("--out", required=True, help="output .npz")
    ap.add_argument("--max-packets", type=int, default=None)
    a = ap.parse_args()
    paths = sorted(p for g in a.pcaps for p in glob.glob(g))
    cols = read_pcap(paths, a.max_packets)
    fl = to_flows(cols)
    info = summarize(fl)
    info.update(files=[os.path.basename(p) for p in paths], skipped_packets=cols["skipped"])
    np.savez_compressed(a.out, **fl, info=np.array(str(info)))
    print(info)


if __name__ == "__main__":
    main()
