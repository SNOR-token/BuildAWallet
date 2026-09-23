#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p src/app
cp ../human_worker.py src/main.py
cp ../app/brain.py ../app/catalog.py src/app/
touch src/app/__init__.py
