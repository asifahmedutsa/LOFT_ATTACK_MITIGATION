# Real traffic traces

The related work replays real background traffic (see
`experiments_from_related_work.md`, item E2): IMC-10 university data-centre traces
(SFTO-Guard, FTMaster, FTODefender, FTOP, ALFO-Guard, FloRa, rDefender, FTShield) or
`bigFlows.pcap` (DMS-BTT). The simulator can replay either as the benign traffic of a
*trace domain* (`loftbench/trace.py`, `TRACE_DOMAINS`). Attack traffic is still
generated, as in every related paper.

The files are large and not in git. They live in `loft_project/traces/` (ignored) or in
the directory named by `LOFT_TRACE_DIR`.

## Sources

| Trace | Used by | Size | Source |
|---|---|---|---|
| `bigFlows.pcap` | DMS-BTT | 368 MB, 791,615 packets, 5 min, a busy private network's Internet access point | `https://s3.amazonaws.com/tcpreplay-pcap-files/bigFlows.pcap` (linked from the tcpreplay sample-captures page) |
| IMC-10 `univ2_trace.tgz` | FTOP, FTShield, others | 1.4 GB compressed; payloads nulled, IPs SHA-1 anonymised | The original page (`pages.cs.wisc.edu/~tbenson/IMC10_Data.html`) now returns 404. An Internet Archive copy: `https://web.archive.org/web/2024id_/https://pages.cs.wisc.edu/~tbenson/IMC_DATA/univ2_trace.tgz` |
| IMC-10 `univ1_trace.tgz` | FTMaster, FloRa, rDefender | — | Not reachable (archive returns 404); the author asks for e-mail requests (Benson et al., IMC 2010) |

Checksums of the downloaded files are in `traces/SHA256SUMS`.

## Convert once

```bash
python -m loftbench.pcapflows traces/bigFlows.pcap --out traces/bigflows.npz
```

```bash
python -m loftbench.pcapflows "traces/univ2/univ2_pt*" --out traces/univ2.npz
```

`pcapflows` keeps IPv4 TCP/UDP/ICMP packets, groups them into directional 5-tuple flows
(one OpenFlow entry each) and keeps wire lengths.

## Converted traces

| Trace | IPv4 packets kept | Skipped | Directional flows | Span | Native rate | Mean size | sha256 |
|---|---|---|---|---|---|---|---|
| bigFlows | 790,893 | 722 | 40,547 | 300 s | 2,636 pps, 135 flows/s | 449 B | `2b630291…c42dc141` |
| univ2 (`univ2_pt1`, first 3,000,000 packets) | 3,000,000 | 38,559 | 17,437 | 332 s | 9,033 pps, 52.5 flows/s | 749 B | `3da91e8f…` (whole `univ2_trace.tgz`) |

Sanity check (training seeds 1000–1001, no defense, 300 s): bigFlows replayed at 1,200 pps
keeps about 1,400 benign entries in the table before the attack (synthetic D1: about 980),
never overflows on its own, and DMS-BTT setting A2 overflows it from about 113 s
(57.6 % of benign flows harmed; synthetic D1: 127 s, 47.7 %).

## How a trace is replayed

- **Rate.** Trace time is stretched so the total benign rate equals the profile's
  `rate_pps`, the effect of `tcpreplay --pps`: 1,200 packets/s for bigFlows (DMS-BTT: four
  user hosts at 300 each), 1,000 for univ2 (FTOP).
- **Seeds.** Each seed starts the replay at a different offset and wraps around the end
  of the trace; the same seed always gives the same benign traffic.
- **Ports.** Each flow is tied to a user host by its anchor address, so both directions of
  a client's traffic enter on the same port, as when a host replays the trace with
  tcpreplay. For bigFlows the anchor is the private (RFC 1918) endpoint; for the
  anonymised univ2 trace it is the source.
- **Labels.** Every trace flow is benign, as in the papers that replay these traces.

## Limitations

- One replay is split over the user hosts by client, rather than every host replaying
  the whole trace as in DMS-BTT; the total packet and flow rates are the same.
- Replaying at a lower rate stretches inter-packet gaps; flows whose stretched gaps
  exceed the idle timeout lose their entries more often than in the original capture.
- bigFlows is 5 minutes long, so long episodes reuse it from a different offset.
