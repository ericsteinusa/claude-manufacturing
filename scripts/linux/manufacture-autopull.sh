#!/bin/bash
set -e
REPO_DIR=/home/eric/tester/manufacture
VENV_PY=/home/eric/tester/virt/bin/python
VENV_PIP=/home/eric/tester/virt/bin/pip

cd "$REPO_DIR"
sudo -u eric git fetch origin main --quiet

LOCAL=$(sudo -u eric git rev-parse main)
REMOTE=$(sudo -u eric git rev-parse origin/main)

# is-active is queried a lot below; `|| true` because set -e would abort on
# the non-zero it returns for anything but "active".
service_state() { systemctl is-active manufacture.service 2>/dev/null || true; }
service_restarts() { systemctl show manufacture.service -p NRestarts --value 2>/dev/null || true; }

log_service_detail() {
    systemctl status manufacture.service --no-pager -n 12 2>&1 |
        while IFS= read -r line; do
            logger -t manufacture-autopull "    svc: $line"
        done
}

# Runs the check-then-restart safety gate against whatever is currently
# checked out (its caller is responsible for $LOCAL already matching the
# working tree). Shared by the "new commits, just merged" path and the
# "nothing new to pull, but the running process is stale anyway" path
# below -- both need the identical gate before touching the live service.
# Exits the whole script on a hard failure (restart didn't take), same as
# the inline logic this replaced did; returns normally when checks fail,
# since a failed check/test suite is not itself a script failure.
run_checks_and_restart() {
    sudo -u eric "$VENV_PIP" install -q -r requirements.txt

    if ! (sudo -u eric "$VENV_PY" manage.py check && sudo -u eric "$VENV_PY" -m pytest tests/ -q); then
        logger -t manufacture-autopull "Checks FAILED -- service NOT restarted, still running previous commit"
        return 0
    fi

    logger -t manufacture-autopull "Checks passed, restarting service"

    # Log the OUTCOME, not just the intent. `systemctl restart` returns 0
    # once the process has been SPAWNED, not once it is serving: for
    # Type=simple a runserver that dies immediately (port already held, bad
    # .env, DB auth) still exits zero here, after which Restart=on-failure
    # cycles it forever. This message used to be the only record of a
    # restart -- the same defect the Windows script had, where the box
    # served stale code for weeks behind a log full of apparent successes.
    restarts_before=$(service_restarts)
    if ! systemctl restart manufacture.service; then
        logger -t manufacture-autopull "Restart FAILED (systemctl restart returned non-zero) -- repo is at $LOCAL but the server may still be serving older code."
        log_service_detail
        exit 1
    fi

    # A single is-active sample cannot tell a healthy server from a crash
    # loop: during auto-restart the unit reads "active" for the moment
    # between spawn and the child's bind failure. Wait for active, then
    # confirm it is STILL active a few seconds later and that systemd has
    # not counted another auto-restart in the meantime.
    up=0
    for _ in $(seq 1 20); do
        sleep 0.5
        if [ "$(service_state)" = "active" ]; then up=1; break; fi
    done
    if [ "$up" = 1 ]; then
        sleep 4
        if [ "$(service_state)" != "active" ] || [ "$(service_restarts)" != "$restarts_before" ]; then
            up=0
        fi
    fi

    if [ "$up" = 1 ]; then
        logger -t manufacture-autopull "Restart OK -- now serving $LOCAL"
    else
        logger -t manufacture-autopull "Restart FAILED -- repo is at $LOCAL but the service is not staying up (auto-restarts: $restarts_before -> $(service_restarts))."
        log_service_detail
        exit 1
    fi
}

if [ "$LOCAL" = "$REMOTE" ]; then
    # Health check on the quiet path. Restart=on-failure recovers a one-off
    # crash, but it cannot fix a server that fails every start for the same
    # reason -- a stale process holding :8000, a bad .env, DB auth. That
    # state is invisible from here: the unit sits in activating/auto-restart
    # forever while this script exits 0 every two minutes with nothing to
    # say. Observed live -- manufacture.service crash-looped 4000+ times
    # across eight hours while an unrelated leftover dev server happened to
    # hold the port, so the app still answered and nothing flagged it.
    if [ "$(service_state)" != "active" ]; then
        logger -t manufacture-autopull "Nothing to pull, but manufacture.service is $(service_state) (auto-restarts: $(service_restarts)) -- the server is NOT up."
        log_service_detail
        exit 1
    fi

    # "Active" only means a process is running -- it does not mean that
    # process is actually serving $LOCAL. If main was advanced by anything
    # other than this script (e.g. an interactive `git pull`/`checkout` in
    # this same working directory -- REPO_DIR is a normal working checkout,
    # not a dedicated deploy-only clone, so this happens routinely during
    # ordinary development), the running process can be silently stale even
    # though there is "nothing new to pull" from this script's own point of
    # view, since it only ever compares git refs. Observed live 2026-09-10:
    # exactly this happened for hours with zero log symptom, because this
    # quiet path never checked what the *running* process actually had
    # loaded. /healthz/ already tracks that distinction (its own process
    # sha vs. disk_sha) -- ask it rather than re-deriving the same check
    # from raw git state.
    code_stale=$(curl -s -m 5 http://127.0.0.1:8000/healthz/ 2>/dev/null |
        sudo -u eric "$VENV_PY" -c \
            "import json, sys
try:
    print(json.load(sys.stdin)['version']['code_stale'])
except Exception:
    print('unknown')" 2>/dev/null)

    if [ "$code_stale" != "True" ]; then
        exit 0
    fi

    logger -t manufacture-autopull "Nothing new on main, but /healthz/ reports the running process is stale -- restarting to catch up to $LOCAL."
    run_checks_and_restart
    exit 0
fi

logger -t manufacture-autopull "New commits detected ($LOCAL -> $REMOTE), pulling"

# Never `git pull origin main --ff-only` here. That form decided based on
# `rev-parse main` but pulled into HEAD, so whenever this checkout sat on
# a feature branch (any interactive session working in this directory) the
# pull targeted that branch instead: `main` never moved, the next cycle
# detected the identical delta, and the deploy stalled silently while the
# log kept announcing "New commits detected". Observed live -- five
# consecutive cycles reporting the same source SHA. Worse, on a
# freshly-created branch with no commits of its own the --ff-only pull
# SUCCEEDS and fast-forwards that branch onto origin/main, moving
# someone's work under them with no warning.
#
# The two cases need different mechanisms, and neither is `pull`:
#   on main      -> merge --ff-only, which advances the working tree too
#   anywhere else-> fetch main:main, which moves the ref only. (git
#                   REFUSES this when main is checked out, so it cannot
#                   substitute for the first case.)
CURRENT=$(sudo -u eric git symbolic-ref --short -q HEAD || echo "DETACHED")

if [ "$CURRENT" != "main" ]; then
    # Keep the ref current so the box is ready to deploy the moment main
    # is checked out again, but do NOT restart: the working tree holds
    # someone else's branch, and serving that is not what was asked for.
    if ! sudo -u eric git fetch origin main:main --quiet; then
        logger -t manufacture-autopull "main has diverged from origin -- left alone."
        exit 1
    fi
    logger -t manufacture-autopull "main advanced to $REMOTE but working tree is on '$CURRENT' -- not restarting; deploy resumes when main is checked out."
    exit 0
fi

if ! sudo -u eric git merge --ff-only "$REMOTE" --quiet; then
    logger -t manufacture-autopull "Could not fast-forward main (diverged?) -- service NOT restarted."
    exit 1
fi

LOCAL="$REMOTE"
run_checks_and_restart
