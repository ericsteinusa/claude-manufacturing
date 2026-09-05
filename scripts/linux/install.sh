#!/bin/bash
# Install the Linux deploy units. Counterpart to
# scripts/windows/register-scheduled-tasks.ps1.
#
# Re-running is safe: it replaces whatever is currently installed.
#
# The Windows box runs its autopull straight out of the repo
# (C:\tester\manufacture\scripts\windows\...), so a pull updates the
# deploy tooling itself. This mirrors that: the loose
# /home/eric/tester/manufacture-autopull.sh that systemd currently points
# at becomes a symlink into the repo, leaving the unit file untouched so
# no sudo is needed for the link step.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_SRC="$REPO_DIR/scripts/linux/manufacture-autopull.sh"
LEGACY_PATH="$HOME/tester/manufacture-autopull.sh"
UNIT_SRC="$REPO_DIR/scripts/linux/systemd"

echo "repo:   $REPO_DIR"
echo "script: $SCRIPT_SRC"

if [ ! -x "$SCRIPT_SRC" ]; then
    echo "ERROR: $SCRIPT_SRC missing or not executable" >&2
    exit 1
fi
bash -n "$SCRIPT_SRC" || { echo "ERROR: $SCRIPT_SRC has a syntax error" >&2; exit 1; }

# --- point the legacy path at the repo copy --------------------------------
if [ -L "$LEGACY_PATH" ]; then
    echo "already a symlink -> $(readlink "$LEGACY_PATH")"
elif [ -e "$LEGACY_PATH" ]; then
    backup="$LEGACY_PATH.bak-$(date +%Y%m%d-%H%M%S)"
    echo "backing up existing file -> $backup"
    cp -p "$LEGACY_PATH" "$backup"
fi
ln -sfn "$SCRIPT_SRC" "$LEGACY_PATH"
echo "linked: $LEGACY_PATH -> $(readlink "$LEGACY_PATH")"

# --- systemd units (needs root; skipped with a note if unavailable) --------
if [ "$(id -u)" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo
    echo "Skipping systemd unit install (needs root). The symlink above is"
    echo "enough to pick up script changes, since the unit already points at"
    echo "$LEGACY_PATH. To sync the unit files themselves, run:"
    echo "  sudo cp $UNIT_SRC/*.service $UNIT_SRC/*.timer /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable --now manufacture-autopull.timer"
    exit 0
fi

sudo cp "$UNIT_SRC"/*.service "$UNIT_SRC"/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now manufacture-autopull.timer
echo "systemd units installed and timer enabled."
systemctl list-timers manufacture-autopull.timer --all --no-pager | head -3
