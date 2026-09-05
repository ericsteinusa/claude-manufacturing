#!/bin/bash
set -e
REPO_DIR=/home/eric/tester/manufacture
VENV_PY=/home/eric/tester/virt/bin/python
VENV_PIP=/home/eric/tester/virt/bin/pip

cd "$REPO_DIR"
sudo -u eric git fetch origin main --quiet

LOCAL=$(sudo -u eric git rev-parse main)
REMOTE=$(sudo -u eric git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
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
sudo -u eric "$VENV_PIP" install -q -r requirements.txt

if sudo -u eric "$VENV_PY" manage.py check && sudo -u eric "$VENV_PY" -m pytest tests/ -q; then
    logger -t manufacture-autopull "Checks passed, restarting service"
    systemctl restart manufacture.service
else
    logger -t manufacture-autopull "Checks FAILED after pull -- service NOT restarted, still running previous commit"
fi
