import random
from typing import Dict, List


def sample_attack_bursts(
    t1_range: List[float], step_s: int, max_packets_m: int, seed: int = 42
) -> List[Dict[str, float]]:
    """
    Generate LFTO burst schedule:
      N_i = N_{i-1} + S
    until cumulative malicious packets reach M.
    """
    rng = random.Random(seed)
    bursts = []
    cumulative = 0
    ni = 0
    time_s = 0.0

    while cumulative < max_packets_m:
        ni += step_s
        to_send = min(ni, max_packets_m - cumulative)
        t = rng.uniform(t1_range[0], t1_range[1])
        time_s += t
        cumulative += to_send
        bursts.append(
            {
                "burst_time_s": round(time_s, 3),
                "interval_s": round(t, 3),
                "new_packets": int(to_send),
                "cumulative_packets": int(cumulative),
            }
        )

    return bursts

