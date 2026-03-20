#!/bin/bash

# ajaxchess_service_update_and_restart.sh
#
# Checks for new commits on origin/main.  If changes are found:
#   1. Pulls the latest code
#   2. Installs/updates Python dependencies
#   3. Runs init_db() to create any new database tables
#   4. Restarts the systemd service
#
# Recommended cron (runs every 5 minutes):
#   */5 * * * * /home/ubuntu/ajaxchess/scripts/ajaxchess_service_update_and_restart.sh >> /var/log/ajaxchess_deploy.log 2>&1

# ── Configuration ─────────────────────────────────────────────────────────────
REPO_DIR="/home/ubuntu/ajaxchess"
VENV_DIR="$REPO_DIR/venv"
SERVICE_NAME="ajaxchess"

# ── Navigate to repo ──────────────────────────────────────────────────────────
cd "$REPO_DIR" || { echo "Error: REPO_DIR $REPO_DIR not found"; exit 1; }

# ── Fetch remote changes ──────────────────────────────────────────────────────
git fetch origin > /dev/null 2>&1

LOCAL_COMMIT=$(git rev-parse HEAD)
REMOTE_COMMIT=$(git rev-parse origin/main)

if [ "$LOCAL_COMMIT" = "$REMOTE_COMMIT" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') Up to date ($LOCAL_COMMIT). Nothing to do."
    exit 0
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') Changes detected: $LOCAL_COMMIT -> $REMOTE_COMMIT"

# ── Stash any local changes so the pull is clean ─────────────────────────────
if [[ $(git status --porcelain) ]]; then
    echo "Warning: uncommitted local changes found — stashing."
    git stash
fi

# ── Pull ──────────────────────────────────────────────────────────────────────
git pull origin main || { echo "Error: git pull failed"; exit 1; }
echo "Pull complete."

# ── Update Python dependencies ────────────────────────────────────────────────
echo "Installing/updating Python dependencies..."
"$VENV_DIR/bin/pip" install -r "$REPO_DIR/requirements.txt" --quiet \
    || { echo "Warning: pip install reported errors"; }

# ── Apply any new database tables (SQLAlchemy create_all is idempotent) ───────
echo "Running database migrations (init_db)..."
"$VENV_DIR/bin/python" -c "
import sys
sys.path.insert(0, '$REPO_DIR')
from database import init_db
init_db()
print('init_db() complete.')
" || { echo "Error: init_db() failed"; exit 1; }

# ── Restart the service ───────────────────────────────────────────────────────
echo "Restarting service: $SERVICE_NAME..."
sudo systemctl restart "$SERVICE_NAME" \
    || { echo "Error: failed to restart $SERVICE_NAME"; exit 1; }

echo "$(date '+%Y-%m-%d %H:%M:%S') Deploy complete. Service $SERVICE_NAME restarted."
