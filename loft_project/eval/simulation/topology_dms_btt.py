from dataclasses import dataclass


@dataclass
class TopologyConfig:
    controller_count: int = 1
    switch_count: int = 2
    user_hosts: int = 6
    attacker_hosts: int = 2
    bottleneck_mbps: int = 250
    bottleneck_latency_ms: int = 15
    host_link_mbps: int = 1000
    host_latency_ms: int = 2
    flow_table_size: int = 3500
    idle_timeout_s: int = 10


def describe_topology(cfg: TopologyConfig) -> str:
    return (
        f"Controller={cfg.controller_count}, Switches={cfg.switch_count}, "
        f"Users={cfg.user_hosts}, Attackers={cfg.attacker_hosts}, "
        f"Bottleneck={cfg.bottleneck_mbps}Mbps/{cfg.bottleneck_latency_ms}ms, "
        f"FlowTable={cfg.flow_table_size}, IdleTimeout={cfg.idle_timeout_s}s"
    )

