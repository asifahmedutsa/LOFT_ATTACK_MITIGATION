#!/bin/bash
# Flash crowds (docs/flash_prereg.md): the burst size by the selection rule of section 3, then
# 8 methods x seeds 4165-4167 on T1B F<k> (24 runs), by seed then method, and a second pass that
# reruns once every run that failed or was invalid. Run names fc_T1B_F<k>_<method>_s<seed>.
#   bash testbed/campaign_flash.sh
set -u
cd "$(dirname "$0")/.."
OUT=results/testbed_flash
mkdir -p "$OUT"
RUNS="$HOME/loft-runs"
METHODS="none ftmaster ftop ftodefender flora dms-btt-h1 rdefender fever-fl-ll"

run() {   # traffic seed methods tag
    while pgrep -x chrome >/dev/null || pgrep -x zoom >/dev/null; do sleep 60; done
    E5_TAG=$4 E5_DUR=300 E5_DOM=T1B E5_TOPO=tree3 E5_BSCALE=0.5 \
        E5_VARS="$1" E5_DEFS="$3" E5_SEEDS="$2" bash testbed/matrix_e5.sh
}

s11_max() {   # run dir -> s11's largest poll (entries), or 0
    python3 - "$1/switch_T1B_s11.csv" <<'EOF'
import csv, sys
try:
    print(max(int(float(r["entries"])) for r in csv.DictReader(open(sys.argv[1]))))
except Exception:
    print(0)
EOF
}

if [ -f "$OUT/selected_k.txt" ]; then
    K=$(cat "$OUT/selected_k.txt")
else
    K=""
    for k in 4 6 8; do
        d="$RUNS/flsel_T1B_F${k}_none_s4165"
        run "F$k" 4165 none flsel || exit 1
        [ -f "$d/summary.txt" ] || run "F$k" 4165 none flsel || exit 1
        [ -f "$d/summary.txt" ] || { echo "selection run F$k failed twice"; exit 1; }
        m=$(s11_max "$d")
        echo "selection F$k: s11 largest poll $m entries (rule: >= 3150)" | tee -a "$OUT/selection.txt"
        if [ "$m" -ge 3150 ]; then K=$k; break; fi
    done
    [ -n "$K" ] || { K=8; echo "F8 did not fill s11; the study runs at F8 (section 3)" | tee -a "$OUT/selection.txt"; }
    echo "$K" > "$OUT/selected_k.txt"
fi
echo "## flash crowds at F$K"

for pass in 1 2; do
    echo "## pass $pass start $(date '+%F %T')"
    for s in 4165 4166 4167; do
        run "F$K" "$s" "$METHODS" fc || exit 1
    done
done
{ echo "# Flash-crowd reruns (runs invalid or failed once; a run listed twice is missing)"; echo
  ls "$RUNS/_failed" 2>/dev/null | grep -E '^fc_T1B_F' | sed 's/^/- /'; } > "$OUT/reruns.md"
echo "## flash crowds done $(date '+%F %T')"
