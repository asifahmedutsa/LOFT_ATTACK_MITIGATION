"""Export every testbed defense's models and settings next to the v2.1 models.

    python -m loftbench.export_testbed            # writes into results/v21/exported/

Per synthetic domain D1-D3: dmsB_state_<D>.json and dmsB_flow_<D>.json (CatBoost JSON of
revision 2's DMS-BTT models, evaluated in the controller by loftbench.cbjson), plus
defenses.json with the fixed settings: DMS-BTT tuned + blocklist (revision 2, family B) and
PortGuard as selected in step 4b. v21_<D>.json is written by `loftbench.v21 --stages export`.

Per trace domain T1-T3 (revision 5): the DMS-BTT models trained on that trace, and
v21_<T>.json, the same federated model as v21_D1.json with the threshold recalibrated on the
trace's validation runs (exactly what revision 5 evaluates).
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
    ap.add_argument("--rev5", default="results/revision5")
    ap.add_argument("--out", default="results/v21/exported")
    a = ap.parse_args()
    m, _ = pickle.load(open(os.path.join(a.rev2, "models.pkl"), "rb"))
    B = json.load(open(os.path.join(a.rev2, "selected.json")))["selected"]["B"]
    P = json.load(open(os.path.join(a.rev4b, "selected.json")))["selected"]
    for d in ("D1", "D2", "D3"):
        export(m[f"state/{d}"].m, os.path.join(a.out, f"dmsB_state_{d}.json"))
        export(m[f"flow/{B['numb']}/{d}"].m, os.path.join(a.out, f"dmsB_flow_{d}.json"))
    m5, taus5 = pickle.load(open(os.path.join(a.rev5, "models.pkl"), "rb"))
    v21 = json.load(open(os.path.join(a.out, "v21_D1.json")))
    for t in ("T1", "T2", "T3"):
        export(m5[f"dms_state/{t}"].m, os.path.join(a.out, f"dmsB_state_{t}.json"))
        export(m5[f"dms_flow/{t}"].m, os.path.join(a.out, f"dmsB_flow_{t}.json"))
        json.dump(dict(v21, tau=float(taus5[f"fedavg/{t}"]),
                       tau_source=f"{a.rev5}/models.pkl fedavg/{t}"),
                  open(os.path.join(a.out, f"v21_{t}.json"), "w"))
    cfg = dict(dms_blocklist=dict(h1=B["h1"], h2=B["h2"], p_thresh=B["p"], numb_mode=B["numb"],
                                  blocklist_s=B["block"], source=f"{a.rev2}/selected.json (B)"),
               portguard={k: P[k] for k in ("mode", "share", "q", "rho_q", "hold_s", "tau_s")},
               portguard_source=f"{a.rev4b}/selected.json")
    json.dump(cfg, open(os.path.join(a.out, "defenses.json"), "w"), indent=2)
    print("exported DMS-BTT models for D1-D3 and T1-T3, v21_T1-T3 and", json.dumps(cfg))


if __name__ == "__main__":
    main()
