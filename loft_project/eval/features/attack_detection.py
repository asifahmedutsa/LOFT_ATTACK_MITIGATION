import numpy as np
import pandas as pd


def compute_apit(flow_table_df: pd.DataFrame) -> float:
    """Compute average packet inter-arrival time (APIT) from flow table rows."""
    if flow_table_df.empty:
        return 0.0

    nump = flow_table_df["nump"].to_numpy(dtype=float)
    duration = flow_table_df["duration_s"].to_numpy(dtype=float)
    pit = np.divide(duration, nump, out=np.zeros_like(duration), where=nump > 0)
    return float(pit.mean()) if pit.size else 0.0


def compute_fn(flow_table_df: pd.DataFrame) -> int:
    """Compute current flow table entry count (FN)."""
    return int(len(flow_table_df))


def build_state_features(flow_table_df: pd.DataFrame) -> dict:
    """Build DMS-BTT state detection features."""
    return {
        "FN": compute_fn(flow_table_df),
        "APIT": compute_apit(flow_table_df),
    }


def derive_state_label(flow_count: int, flow_table_size: int) -> int:
    """
    Derive coarse LFTO state label:
      0: normal
      1: attack growth stage
      2: overflow stage
    """
    if flow_count >= flow_table_size:
        return 2
    if flow_count > 0.75 * flow_table_size:
        return 1
    return 0

