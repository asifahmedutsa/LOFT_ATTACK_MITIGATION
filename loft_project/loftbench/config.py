"""Experiment configuration: switch parameters, domain traffic profiles and
LFTO attack variants. Everything an experiment depends on is declared here so
that a run is fully described by (domain, variant, seed, defense, SimConfig)."""
from dataclasses import dataclass, field, asdict
from typing import Dict, Tuple


@dataclass(frozen=True)
class SimConfig:
    capacity: int = 3500          # total flow-table entries (DMS-BTT setting)
    infra_rules: int = 1          # table-miss rule occupies one entry
    idle_timeout: float = 10.0    # seconds (DMS-BTT setting)
    dt: float = 0.1               # simulation tick (s)
    poll_interval: float = 1.0    # flow-stats polling period (s)
    duration: float = 300.0       # episode length (s)
    attack_start: float = 50.0    # DMS-BTT offline onset

    def to_dict(self):
        return asdict(self)


# Benign flow kinds. Each kind is a family of flows with its own packet-count,
# inter-arrival and size distribution. "periodic" flows (keepalives, IoT
# telemetry, heartbeats) send one small packet every few seconds and are the
# realistic hard negatives for LFTO detection.
FLOW_KINDS = ("dns", "mice", "elephant", "periodic", "interactive", "flash")


@dataclass(frozen=True)
class DomainProfile:
    name: str
    new_flow_rate: float                       # benign flow arrivals per second
    mix: Dict[str, float]                      # probability of each flow kind
    n_clients: int = 400                       # benign source-IP pool
    zipf_a: float = 1.15                       # source popularity skew
    periodic_period: Tuple[float, float] = (1.0, 9.5)
    periodic_duration: Tuple[float, float] = (20.0, 120.0)
    elephant_pareto: Tuple[float, float] = (1.5, 50.0)  # (alpha, x_m)
    flash_events: int = 0                      # flash crowds per 300 s
    flash_rate: float = 0.0                    # extra flows/s during a crowd
    flash_len: float = 10.0


DOMAINS: Dict[str, DomainProfile] = {
    # Enterprise/campus: bigFlows-like mixture.
    "D1": DomainProfile(
        name="D1-enterprise", new_flow_rate=85.0,
        mix={"dns": .35, "mice": .43, "elephant": .03, "periodic": .07, "interactive": .12},
    ),
    # IoT edge: many low-rate periodic telemetry flows (hard negatives).
    "D2": DomainProfile(
        name="D2-iot", new_flow_rate=60.0,
        mix={"dns": .25, "mice": .30, "elephant": .01, "periodic": .35, "interactive": .09},
        n_clients=1200, zipf_a=1.05, periodic_period=(2.0, 9.8),
    ),
    # Cloud front-end: more elephants and benign flash crowds from many sources.
    "D3": DomainProfile(
        name="D3-cloud", new_flow_rate=65.0,
        mix={"dns": .25, "mice": .45, "elephant": .07, "periodic": .08, "interactive": .15},
        flash_events=2, flash_rate=120.0, flash_len=12.0,
    ),
}


@dataclass(frozen=True)
class AttackVariant:
    """LFTO attack following the DMS-BTT recurrence N_i = N_{i-1} + S.

    Every burst re-sends packets on all live attack flows (refreshing them
    before the idle timeout) and opens S new flows, until each attacker holds
    M flows. Inter-burst gap t1 ~ U(t1_range).
    """
    name: str
    step: int                                  # S
    t1_range: Tuple[float, float]
    max_flows: int = 1700                      # M per attacker
    pkts_per_refresh: Tuple[int, int] = (1, 1)
    size_mode: str = "fixed"                   # "fixed" (64 B) | "benign"
    src_mode: str = "host"                     # "host" | "pool" | "spoof"
    burst_pps: float = 1500.0                  # send rate within a burst
    pulse_on: float = 0.0                      # >0 enables on/off pulsing
    pulse_off: float = 0.0
    n_attackers: int = 2


VARIANTS: Dict[str, AttackVariant] = {
    # DMS-BTT reference parameter sets.
    "A1": AttackVariant("A1-dms-s75", 75, (5.0, 8.5), src_mode="pool"),
    "A2": AttackVariant("A2-dms-s100", 100, (5.5, 9.0), src_mode="host"),
    "A3": AttackVariant("A3-dms-s125", 125, (6.0, 9.5), src_mode="pool"),
    # Stronger adversaries.
    "A4": AttackVariant("A4-mimic", 100, (6.0, 9.5), pkts_per_refresh=(1, 3),
                        size_mode="benign", src_mode="pool"),
    "A5": AttackVariant("A5-spoof", 100, (5.5, 9.0), src_mode="spoof"),
    "A6": AttackVariant("A6-slowfill", 45, (8.0, 9.8), pkts_per_refresh=(1, 2),
                        size_mode="benign", src_mode="spoof"),
    "A7": AttackVariant("A7-pulse", 300, (5.0, 8.0), src_mode="host",
                        pulse_on=60.0, pulse_off=30.0),
}

# Heterogeneous attack exposure used for training. A6 is never seen in
# training by any controller (zero-day variant).
EXPOSURE: Dict[str, Tuple[str, ...]] = {
    "D1": ("A1", "A4"),
    "D2": ("A2", "A5"),
    "D3": ("A3", "A7"),
}
UNSEEN_VARIANTS = ("A6",)
