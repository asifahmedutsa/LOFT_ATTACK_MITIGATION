#!/bin/bash
# Install (or update) passwordless access to the LOFT testbed for the invoking user.
#
#   cd loft_project && sudo bash testbed/root/install.sh
#
# What it does, all as root:
#   1. Copies a snapshot of loftbench/, testbed/, the exported models, the trace replay files
#      (traces/*.npz) and the Ryu environment's Python packages to /opt/loft-testbed
#      (root-owned, not writable by users).
#   2. Installs the validating wrapper /usr/local/sbin/loft-testbed (root-owned, mode 0755).
#   3. Adds /etc/sudoers.d/loft-testbed allowing ONLY that wrapper without a password,
#      after checking the file with visudo.
# Rerun it after the testbed code changes; the snapshot does not follow edits in the repository.
# Remove everything with:  sudo bash testbed/root/install.sh --uninstall
set -euo pipefail
export PATH=/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin

[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
USER_NAME="${SUDO_USER:?run with sudo from your own account}"
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
BASE=/opt/loft-testbed
WRAPPER=/usr/local/sbin/loft-testbed
SUDOERS=/etc/sudoers.d/loft-testbed

if [ "${1:-}" = "--uninstall" ]; then
    rm -f "$SUDOERS" "$WRAPPER"
    rm -rf "$BASE"
    echo "removed $SUDOERS, $WRAPPER and $BASE"
    exit 0
fi

SRC="$(cd "$(dirname "$0")/../.." && pwd)"           # loft_project/
SITE="$USER_HOME/ryu-env/lib/python3.8/site-packages"
[ -d "$SRC/loftbench" ] && [ -d "$SRC/testbed" ] || { echo "cannot find loft_project at $SRC" >&2; exit 1; }
[ -d "$SITE" ] || { echo "missing $SITE (the Ryu environment)" >&2; exit 1; }
[ -x /usr/bin/python3.8 ] || { echo "missing /usr/bin/python3.8" >&2; exit 1; }

NEW="$BASE.new"
rm -rf "$NEW"
install -d -m 0755 "$NEW/code" "$NEW/bin" "$NEW/code/results/v21"
cp -r "$SRC/loftbench" "$SRC/testbed" "$NEW/code/"
cp -r "$SRC/results/v21/exported" "$NEW/code/results/v21/"
# Replay files for the trace domains T1-T3 (written by loftbench.pcapflows; not in git).
install -d -m 0755 "$NEW/code/traces"
for f in bigflows.npz univ2.npz; do
    if [ -f "$SRC/traces/$f" ]; then cp "$SRC/traces/$f" "$NEW/code/traces/"; fi
done
cp -r "$SITE" "$NEW/py38-site"
# Ryu is an editable install (its source lives in the user's home); copy the package itself and
# drop every link back into user-writable directories.
RYU_SRC="$("$USER_HOME/ryu-env/bin/python" -c 'import os, ryu; print(os.path.dirname(ryu.__file__))')"
cp -r "$RYU_SRC" "$NEW/py38-site/ryu"
rm -f "$NEW/py38-site/ryu.egg-link" "$NEW/py38-site/easy-install.pth"
if grep -lq "$USER_HOME" "$NEW/py38-site"/*.pth 2>/dev/null; then
    echo "a .pth file still points into $USER_HOME; refusing to install" >&2; exit 1
fi
rm -rf "$NEW/code/testbed/root"
find "$NEW" -name __pycache__ -type d -prune -exec rm -rf {} +

# Python 3.8 launchers: boot.py registers the snapshot as a site directory (so its .pth files
# are processed), then runs a script, or a module after "-m".
cat > "$NEW/bin/boot.py" <<PYEOF
import runpy, site, sys
# Like a virtual environment: no system or user package directories, only the snapshot.
sys.path[:] = [p for p in sys.path if "-packages" not in p]
site.addsitedir("$BASE/py38-site")
if sys.argv[1] == "-m":
    mod = sys.argv[2]
    sys.argv = [mod] + sys.argv[3:]
    runpy.run_module(mod, run_name="__main__", alter_sys=True)
else:
    sys.argv = sys.argv[1:]
    runpy.run_path(sys.argv[0], run_name="__main__")
PYEOF
printf '#!/bin/sh\nexec /usr/bin/python3.8 -s %s/bin/boot.py "$@"\n' "$BASE" > "$NEW/bin/python38"
printf '#!/bin/sh\nexec /usr/bin/python3.8 -s %s/bin/boot.py -m ryu.cmd.manager "$@"\n' "$BASE" \
    > "$NEW/bin/ryu-manager"
chmod 0644 "$NEW/bin/boot.py"
chmod 0755 "$NEW/bin/python38" "$NEW/bin/ryu-manager"
chown -R root:root "$NEW"
chmod -R go-w "$NEW"

rm -rf "$BASE.old"
[ -d "$BASE" ] && mv "$BASE" "$BASE.old"
mv "$NEW" "$BASE"
rm -rf "$BASE.old"

sed -e "s|@OUTROOT@|$USER_HOME/loft-runs|" -e "s|@OWNER@|$USER_NAME|" \
    "$SRC/testbed/root/loft-testbed" > "$WRAPPER.tmp"
install -o root -g root -m 0755 "$WRAPPER.tmp" "$WRAPPER"
rm -f "$WRAPPER.tmp"

TMP="$(mktemp)"
echo "$USER_NAME ALL=(root) NOPASSWD: $WRAPPER" > "$TMP"
visudo -cf "$TMP" >/dev/null
install -o root -g root -m 0440 "$TMP" "$SUDOERS"
rm -f "$TMP"

# Sanity check: the snapshot's Ryu and the controller app import as root.
CHK="$(mktemp --suffix=.py)"
echo "import ryu, numpy, ryu.cmd.manager; print(ryu.__file__)" > "$CHK"
"$BASE/bin/python38" "$CHK" | grep -q "^$BASE/py38-site/ryu/" \
    || { echo "sanity check failed: Ryu does not load from $BASE" >&2; rm -f "$CHK"; exit 1; }
rm -f "$CHK"
echo "installed: $WRAPPER (snapshot of $SRC in $BASE); $USER_NAME may now run:"
echo "  sudo -n loft-testbed --domains D1 --variant A2 --defense dualguard --out <run name>"
