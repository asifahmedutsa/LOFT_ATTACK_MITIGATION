"""Replay recorded table snapshots through the controller's own build_defense (testbed Python 3.8,
exported JSON models) and save every poll's decisions, for comparison with the simulator's
original models (loftbench.testbed_baselines --stages crossenv). No root needed.

    ~/ryu-env/bin/python testbed/check_defenses.py <snapshots.npz> <model_dir> <domain> <out.npz> <defense>...
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from loft_ryu_app import build_defense  # noqa: E402


def main():
    snap, model_dir, domain, out = sys.argv[1:5]
    z = np.load(snap)
    n_polls = int(z["n_polls"])
    meta = json.loads(str(z["meta"]))
    res = {}
    for name in sys.argv[5:]:
        d = build_defense(name, model_dir, domain)
        d.reset({"cfg": None, "n_flows": len(z["flow_src"]), "flow_src": z["flow_src"],
                 "flow_port": z["flow_port"], "n_ports": int(z["flow_port"].max()) + 1})
        for i in range(n_polls):
            obs = {k: z[f"{i}_{k}"] for k in ("fids", "pkts", "bytes", "install_t", "X")}
            obs.update(meta[i], capacity=int(z["capacity"]))
            dels, dems = d.on_poll(obs["t"], obs)
            for tag, arr in (("del", dels), ("dem", dems)):
                res[f"{name}|{i}|{tag}"] = np.sort(np.asarray([] if arr is None else arr, np.int64))
    np.savez(out, **res)
    print("saved", len(res), "decision arrays")


if __name__ == "__main__":
    main()
