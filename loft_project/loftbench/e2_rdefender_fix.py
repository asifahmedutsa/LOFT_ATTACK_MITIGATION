"""rDefender per-event fix: re-select (events x gamma) on validation, then test on E2's seeds.

    PYTHONPATH=. ~/.venvs/loft/bin/python loftbench/e2_rdefender_fix.py
"""
import itertools, json, os, sys
os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, ".")
import pandas as pd
from loftbench import e2_baselines as E2, v21
from loftbench.config import DOMAINS, VARIANTS
from loftbench.experiment import SPLITS
OUT = "results/e2_baselines/rdefender_fix"
os.makedirs(OUT, exist_ok=True)
E2._load()
cells = [(d, v, s) for d in DOMAINS for v in list(VARIANTS) + [None] for s in SPLITS["val"]]
grid = [dict(events=e, gamma=g) for e, g in itertools.product(["poll", "replay"], [0.02, 0.05, 0.1])]
df = E2._run([("rdefender", k, *c) for k in grid for c in cells], 4, "rd-select")
df.to_csv(os.path.join(OUT, "selection_validation.csv"), index=False)
c = v21.RULE["constraints"]
att, ben = df[df.variant != "benign"], df[df.variant == "benign"]
g = att.groupby("knobs")[["benign_flows_harmed_frac", "avg_attack_occ_post", "overflow_seconds_post_attack"]].mean()
g = g.join(ben.groupby("knobs").benign_flows_harmed_frac.mean().rename("benign_only_harmed")).reset_index()
g["feasible"] = ((g.avg_attack_occ_post <= c["avg_attack_occ_post_max"]) & (g.overflow_seconds_post_attack <= c["overflow_seconds_post_attack_max"]) & (g.benign_only_harmed <= c["benign_only_impacted_max"]))
best = (g[g.feasible].sort_values("benign_flows_harmed_frac") if g.feasible.any() else g.sort_values("overflow_seconds_post_attack")).iloc[0]
print(g.round(4).to_string(index=False)); print("SELECTED", best.knobs)
sel = json.loads(best.knobs)
json.dump(dict(selected=sel, table=g.to_dict("records")), open(os.path.join(OUT, "selected.json"), "w"), indent=1)
t = E2._run([("rdefender", sel, d, v, s) for d in DOMAINS for v in list(VARIANTS) + [None] for s in E2.TEST_SEEDS], 4, "rd-test")
t.to_csv(os.path.join(OUT, "test_episodes.csv"), index=False)
a = t[t.variant != "benign"]
print("TEST harmed %.2f  attack share %.2f  overflow %.2f  benign-only harmed %.3f" % (100 * a.benign_flows_harmed_frac.mean(), 100 * a.avg_attack_occ_post.mean(), a.overflow_seconds_post_attack.mean(), 100 * t[t.variant == "benign"].benign_flows_harmed_frac.mean()))
