import numpy as np
import pandas as pd


def build_flow_features(flow_table_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build DMS-BTT per-flow features from raw flow-table columns:
      - Numb: cumulative bytes
      - PIT : packet inter-arrival proxy = duration / packets
      - Sizep: average packet size = bytes / packets
    Expected inputs: bytes_count, packet_count, duration_s
    """
    if flow_table_df.empty:
        return pd.DataFrame(columns=["Numb", "PIT", "Sizep"])

    out = pd.DataFrame(index=flow_table_df.index)
    out["Numb"] = flow_table_df["bytes_count"].astype(float)

    packet_count = flow_table_df["packet_count"].astype(float).to_numpy()
    duration_s = flow_table_df["duration_s"].astype(float).to_numpy()
    bytes_count = flow_table_df["bytes_count"].astype(float).to_numpy()

    out["PIT"] = np.divide(
        duration_s, packet_count, out=np.zeros_like(duration_s), where=packet_count > 0
    )
    out["Sizep"] = np.divide(
        bytes_count, packet_count, out=np.zeros_like(bytes_count), where=packet_count > 0
    )
    return out


def label_flows_by_attacker_ip(flow_table_df: pd.DataFrame, attacker_ips: set) -> pd.Series:
    """
    Label flows:
      1 if src_ip belongs to known attacker sources, else 0.
    """
    src = flow_table_df["src_ip"].astype(str)
    return src.apply(lambda ip: 1 if ip in attacker_ips else 0).astype(int)

