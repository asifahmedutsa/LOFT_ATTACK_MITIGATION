"""Ingress-port model for the per-port fair-share guard (revision step 4).

The DMS-BTT topology gives every user host its own access port: four benign
hosts and two attackers per switch. Spoofing changes a packet's source IP, not
the port it arrives on, so the port is the identity an attacker cannot forge.

Scenarios (benign flows are mapped to ports by client address, so one client
always uses one port):

  dedicated    4 benign ports; attacker a on its own port 4 + a (DMS-BTT topology)
  shared       benign clients spread over all 6 ports; attacker a also on port 4 + a
  distributed  benign over 6 ports; every attack flow enters on a random port
               (attacker controls a host behind every port)
"""
import numpy as np

N_PORTS = 6
N_BENIGN_PORTS = {"dedicated": 4, "shared": 6, "distributed": 6}
SCENARIOS = tuple(N_BENIGN_PORTS)


def _mix(x):
    """Deterministic integer hash (splitmix64 finaliser), vectorised."""
    x = (np.asarray(x, np.uint64) + np.uint64(0x9E3779B97F4A7C15))
    x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return x ^ (x >> np.uint64(31))


def assign_ports(traffic, scenario="dedicated"):
    """Set traffic.flow_port in place and return the traffic."""
    if traffic.flow_owner is None:
        raise ValueError("traffic has no flow_owner; build it with build_traffic")
    nb = N_BENIGN_PORTS[scenario]
    own = traffic.flow_owner
    port = (_mix(traffic.flow_src) % np.uint64(nb)).astype(np.int16)
    att = own >= 0
    if scenario == "distributed":
        fid = np.flatnonzero(att)
        port[att] = (_mix(fid + 0x5BD1E995) % np.uint64(N_PORTS)).astype(np.int16)
    else:
        port[att] = (4 + own[att]).astype(np.int16)
    traffic.flow_port = port
    return traffic
