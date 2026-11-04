"""LOFT-Bench: multi-controller low-rate flow-table overflow (LFTO) simulator,
detectors, federated learning, and defenses.

The simulator models what an OpenFlow 1.3 controller can observe: bounded flow
tables, reactive rule installation, idle timeouts, Packet-In / table-full
events, and periodic flow-statistics polling. It does not model link-level
queueing or physical TCAM timing; see docs/methodology_v2.md.
"""
