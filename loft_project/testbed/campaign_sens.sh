#!/bin/bash
# Sensitivity of FEVER to its fixed settings (docs/sensitivity_prereg.md): one smoke run (fever-s-k2,
# G2, seed 4183; not a result), then 6 settings x 5 traffic cases x 3 seeds = 90 runs, by seed, traffic
# case, then setting, and a second pass that reruns once every run that failed or was invalid.
# Attacks and benign only at the campaign's settings (capacity 3,500, seeds 4160-4162); the one-host
# crowd F2H at round 2's (capacity 2,000, seeds 4187-4189). Run names sens_T1B_<variant>_<method>_s<seed>.
#   bash testbed/campaign_sens.sh
set -u
cd "$(dirname "$0")/.."
grep -q "^DRAFT" docs/sensitivity_prereg.md && { echo "docs/sensitivity_prereg.md is still a draft"; exit 1; }
OUT=results/testbed_sens
mkdir -p "$OUT"
RUNS="$HOME/loft-runs"
SETS="fever-s-r60 fever-s-r80 fever-s-k2 fever-s-k4 fever-s-v125 fever-s-v200"

run() {   # traffic seed methods tag [capacity]
    while pgrep -x chrome >/dev/null || pgrep -x zoom >/dev/null; do sleep 60; done
    E5_TAG=$4 E5_DUR=300 E5_DOM=T1B E5_TOPO=tree3 E5_BSCALE=0.5 E5_CAP=${5:-} \
        E5_VARS="$1" E5_DEFS="$3" E5_SEEDS="$2" bash testbed/matrix_e5.sh
}

if [ ! -f "$RUNS/senssmoke_T1B_A2_fever-s-k2_s4183/summary.txt" ]; then
    echo "## smoke $(date '+%F %T')"
    run A2 4183 fever-s-k2 senssmoke || exit 1
    d="$RUNS/senssmoke_T1B_A2_fever-s-k2_s4183"
    [ -f "$d/summary.txt" ] || { echo "smoke run failed; stopping"; exit 1; }
    grep -q "host_block" "$d"/controller_*_flows.csv || { echo "smoke run blocked no host; stopping"; exit 1; }
    echo "smoke ok" | tee "$OUT/smoke.md"
fi

for pass in 1 2; do
    echo "## pass $pass start $(date '+%F %T')"
    for i in 0 1 2; do
        for v in A2 A4 E9P benign; do
            run "$v" $((4160 + i)) "$SETS" sens || exit 1
        done
        run F2H $((4187 + i)) "$SETS" sens 2000 || exit 1
    done
done
{ echo "# Sensitivity study reruns (runs invalid or failed once; a run listed twice is missing)"; echo
  ls "$RUNS/_failed" 2>/dev/null | grep -E '^sens_T1B_' | sed 's/^/- /'; } > "$OUT/reruns.md"
echo "## sensitivity study done $(date '+%F %T')"
