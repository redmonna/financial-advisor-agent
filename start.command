#!/bin/bash
# Financial AI v2 — AG-UI Startup
# Double-click in Finder or run: ./start.command

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "=== Financial AI v2 — AG-UI ==="
echo "Project: $PROJECT_DIR"
echo ""

# --- Python venv ---
if [ ! -d ".venv" ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi

# --- Load .env (export each KEY=VALUE line) ---
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# --- Start backend (uvicorn) ---
echo "Starting backend on http://localhost:8000 ..."
uvicorn agui_server:app --port 8000 &
BACKEND_PID=$!

# --- Start frontend (Next.js) ---
echo "Starting frontend on http://localhost:3000 ..."
(cd chat-ui && npm run dev) &
FRONTEND_PID=$!

# --- Clean shutdown on Ctrl+C or exit ---
cleanup() {
  echo ""
  echo "Shutting down..."
  kill "$FRONTEND_PID" 2>/dev/null
  kill "$BACKEND_PID" 2>/dev/null
  wait "$FRONTEND_PID" 2>/dev/null
  wait "$BACKEND_PID" 2>/dev/null
  echo "Done."
}
trap cleanup INT TERM EXIT

# --- Open browser after servers have a moment to start ---
sleep 3
open "http://localhost:3000"

echo ""
echo "Both servers running. Press Ctrl+C to stop."
echo ""

# Wait for either process to exit
wait -n "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
cleanup
