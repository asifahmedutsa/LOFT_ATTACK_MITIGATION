#!/bin/bash
# Flash crowds, round 2 (docs/flash2_prereg.md): tables of 2,000 entries; the crowd rate by the
# selection rule of section 3, then 8 methods x seeds 4187-4189 x two placements (F<k> spread over the
# benign hosts, F<k>H all from d1h3) = 48 runs, by seed, placement, then method, and a second pass
# that reruns once every run that failed or was invalid. Run names fc2_T1B_F<k>[H]_<method>_s<seed>.
#   bash testbed/campaign_flash2.sh
set -u
cd "$(dirname "$0")/.."
grep -q "preregistration (draft)" docs/flash2_prereg.md && { echo "docs/flash2_prereg.md is still a draft"; exit 1; }
OUT=results/testbed_flash2
mkdir -p "$OUT"
RUNS="$HOME/loft-runs"
CAP=2000
FULL=1800
METHODS="none ftmaster ftop ftodefender flora dms-btt-h1 rdefender fever-fl-ll"

run() {   # traffic seed methods tag
    while pgrep -x chrome >/dev/null || pgrep -x zoom >/dev/null; do sleep 60; done
    E5_TAG=$4 E5_DUR=300 E5_DOM=T1B E5_TOPO=tree3 E5_BSCALE=0.5 E5_CAP=$CAP \
        E5_VARS="$1" E5_DEFS="$3" E5_SEEDS="$2" bash testbed/matrix_e5.sh
}

measure() {   # run dir -> "<s11's largest poll> <drop share %>"
    python3 - "$1" <<'EOF'
import csv, re, sys
d = sys.argv[1]
try:
    m = max(int(float(r["entries"])) for r in csv.DictReader(open(f"{d}/switch_T1B_s11.csv")))
except Exception:
    m = 0
def cov(f):
    out = {}
    for line in open(f):
        x = re.match(r"(\S+)\s+.*total:\s*(\d+)", line)
        if x:
            out[x.group(1)] = int(x.group(2))
    return out
try:
    a, b = cov(f"{d}/ovs_coverage_before.txt"), cov(f"{d}/ovs_coverage_after.txt")
    q = b.get("rconn_queued", 0) - a.get("rconn_queued", 0)
    o = b.get("rconn_overflow", 0) - a.get("rconn_overflow", 0)
    p = 100.0 * o / (q + o) if q + o else 0.0
except Exception:
    p = 100.0
print(m, f"{p:.1f}")
EOF
}

if [ -f "$OUT/selected_k.txt" ]; then
    K=$(cat "$OUT/selected_k.txt")
else
    K=""; FIRST_FILL=""
    for k in 2 3 4 5 6; do
        d="$RUNS/fl2sel_T1B_F${k}_none_s4187"
        run "F$k" 4187 none fl2sel || exit 1
        [ -f "$d/summary.txt" ] || run "F$k" 4187 none fl2sel || exit 1
        [ -f "$d/summary.txt" ] || { echo "selection run F$k failed twice"; exit 1; }
        read -r m p <<< "$(measure "$d")"
        echo "selection F$k: s11 largest poll $m entries (rule: >= $FULL), controller messages dropped $p % (rule: <= 10)" \
            | tee -a "$OUT/selection.txt"
        if [ "$m" -ge "$FULL" ]; then
            [ -z "$FIRST_FILL" ] && FIRST_FILL=$k
            if python3 -c "import sys; sys.exit(0 if float('$p') <= 10 else 1)"; then K=$k; break; fi
        fi
    done
    if [ -z "$K" ] && [ -n "$FIRST_FILL" ]; then
        K=$FIRST_FILL; echo "no k filled s11 with <= 10 % dropped; the study runs at F$K, the first that filled (section 3)" | tee -a "$OUT/selection.txt"
    elif [ -z "$K" ]; then
        K=6; echo "no k filled s11; the study runs at F6, reported as not filled (section 3)" | tee -a "$OUT/selection.txt"
    fi
    echo "$K" > "$OUT/selected_k.txt"
fi
echo "## flash crowds round 2 at F$K and F${K}H"

for pass in 1 2; do
    echo "## pass $pass start $(date '+%F %T')"
    for s in 4187 4188 4189; do
        for v in "F$K" "F${K}H"; do
            run "$v" "$s" "$METHODS" fc2 || exit 1
        done
    done
done
{ echo "# Flash-crowd round 2 reruns (runs invalid or failed once; a run listed twice is missing)"; echo
  ls "$RUNS/_failed" 2>/dev/null | grep -E '^fc2_T1B_F' | sed 's/^/- /'; } > "$OUT/reruns.md"
echo "## flash crowds round 2 done $(date '+%F %T')"
