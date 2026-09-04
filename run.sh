#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi
echo
echo "VaultMind - Sovereign AI Workbench (Team Luminox)"
echo "  Landing : http://127.0.0.1:8080/"
echo "  Console : http://127.0.0.1:8080/console"
echo
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
