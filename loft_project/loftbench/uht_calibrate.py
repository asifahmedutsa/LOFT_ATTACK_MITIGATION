"""FEVER's thresholds on UHt from its benign recording (docs/uht_calibration.md), and the UHt file names
of the baselines that run there.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.uht_calibrate
"""
import json
import os
import pickle
import shutil

import numpy as np
import pandas as pd

from .ensjson import EnsembleJSON
from .models import threshold_at_fpr
from .tbfl import OUT
from .v5 import _would_block

EXP = "results/v21/exported"
RUN = os.path.expanduser("~/loft-runs/tbt_UHt_benign_none_s4190")
SWITCHES = ("s11", "s12", "s13")
CFG = "ens_config_fl_ll.json"
COPY = ("ftmaster_state", "ftmaster_rule", "dmsB_state", "dmsB_flow")


def main():
    cfg = json.load(open(f"{EXP}/{CFG}"))
    ds = pickle.load(open(f"{OUT}/rows.pkl", "rb"))[("UHt", None, 4190)]
    ben = ds.X[ds.y == 0].astype(np.float32)
    tau = float(threshold_at_fpr(EnsembleJSON(EXP, cfg).predict_proba(ben), cfg["budget"]))
    X, busiest, blocked = {}, {}, set()
    for sw in SWITCHES:
        s = pd.read_csv(f"{RUN}/switch_UHt_{sw}.csv")
        m = pd.read_csv(f"{RUN}/switch_UHt_{sw}_macs.csv")
        busiest[sw] = int(m.entries.max())
        X[sw] = 1.5 * busiest[sw]
        blocked |= _would_block(s[["t", "entries"]], m, X[sw])
        busiest[f"{sw}_table_max"] = int(s.entries.max())
    assert not blocked, blocked
    cfg["tau"]["UHt"] = tau
    cfg["rho"]["UHt"] = cfg["rho"]["T1B"]
    cfg["block"]["vol_x"]["UHt"] = X
    json.dump(cfg, open(f"{EXP}/{CFG}", "w"), indent=1)
    for k in COPY:
        shutil.copyfile(f"{EXP}/{k}_T1B.json", f"{EXP}/{k}_UHt.json")
    info = dict(benign_rows=int(len(ben)), tau_UHt=tau, tau_T1B=cfg["tau"]["T1B"], vol_x_UHt=X,
                vol_x_T1B=cfg["block"]["vol_x"]["T1B"], busiest_benign_host=busiest, hosts_blocked_open_loop=0,
                copied=[f"{k}_UHt.json" for k in COPY])
    json.dump(info, open(f"{OUT}/uht_calibration.json", "w"), indent=1)
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
