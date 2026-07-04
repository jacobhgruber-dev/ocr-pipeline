#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv run sphinx-build -b html docs/sphinx docs/build/html "$@"
