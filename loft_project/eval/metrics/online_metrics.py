from typing import Dict

import numpy as np
import pandas as pd


def compute_pa(flow_table_df: pd.DataFrame) -> float:
    """Pa = proportion of attack entries in current flow table."""
    if flow_table_df.empty:
        return 0.0
    if "is_attack_flow" not in flow_table_df.columns:
        raise ValueError("flow_table_df must include 'is_attack_flow' column.")
    return float(flow_table_df["is_attack_flow"].astype(int).mean())


def summarize_online_metrics(timeseries_df: pd.DataFrame) -> Dict[str, float]:
    """
    Expected columns:
      pa, flow_table_usage, packet_in_messages, table_full_messages, cpu_percent,
      overflow_time_s (optional scalar-style repeated or NaN except first row).
    """
    summary = {
        "avg_pa": float(timeseries_df["pa"].mean()),
        "max_pa": float(timeseries_df["pa"].max()),
        "avg_flow_table_usage": float(timeseries_df["flow_table_usage"].mean()),
        "packet_in_messages_total": int(timeseries_df["packet_in_messages"].sum()),
        "table_full_messages_total": int(timeseries_df["table_full_messages"].sum()),
        "avg_cpu_percent": float(timeseries_df["cpu_percent"].mean()),
    }

    if "overflow_time_s" in timeseries_df.columns:
        valid = timeseries_df["overflow_time_s"].dropna()
        summary["earliest_overflow_time_s"] = float(valid.min()) if not valid.empty else float("nan")
    else:
        summary["earliest_overflow_time_s"] = float("nan")

    if np.isnan(summary["earliest_overflow_time_s"]):
        summary["earliest_overflow_time_s"] = -1.0

    return summary

