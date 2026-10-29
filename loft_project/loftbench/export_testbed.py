"""Export every testbed defense's models and settings next to the v2.1 models.

    python -m loftbench.export_testbed            # writes into results/v21/exported/

Per synthetic domain D1-D3: dmsB_state_<D>.json and dmsB_flow_<D>.json (CatBoost JSON of
revision 2's DMS-BTT models, evaluated in the controller by loftbench.cbjson), plus
defenses.json with the fixed settings: DMS-BTT tuned + blocklist (revision 2, family B) and
PortGuard as selected in step 4b. v21_<D>.json is written by `loftbench.v21 --stages export`.
"""
import argparse
import json
import os
import pickle

from .cbjson import export


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rev2", default="results/revision2")
    ap.add_argument("--rev4b", default="results/revision4b")
    ap.add_argument("--out", default="results/v21/exported")
    a = ap.parse_args()
    m, _ = pickle.load(open(os.path.join(a.rev2, "models.pkl"), "rb"))
    B = json.load(open(os.path.join(a.rev2, "selected.json")))["selected"]["B"]
    P = json.load(open(os.path.join(a.rev4b, "selected.json")))["selected"]
    for d in ("D1", "D2", "D3"):
        export(m[f"state/{d}"].m, os.path.join(a.out, f"dmsB_state_{d}.json"))
        export(m[f"flow/{B['numb']}/{d}"].m, os.path.join(a.out, f"dmsB_flow_{d}.json"))
    cfg = dict(dms_blocklist=dict(h1=B["h1"], h2=B["h2"], p_thresh=B["p"], numb_mode=B["numb"],
                                  blocklist_s=B["block"], source=f"{a.rev2}/selected.json (B)"),
               portguard={k: P[k] for k in ("mode", "share", "q", "rho_q", "hold_s", "tau_s")},
               portguard_source=f"{a.rev4b}/selected.json")
    json.dump(cfg, open(os.path.join(a.out, "defenses.json"), "w"), indent=2)
    print("exported DMS-BTT models for D1-D3 and", json.dumps(cfg))


if __name__ == "__main__":
    main()
