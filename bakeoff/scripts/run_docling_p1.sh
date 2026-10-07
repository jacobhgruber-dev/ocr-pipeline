#!/usr/bin/env bash
set -euo pipefail
REPO=/Users/jacobgruber/Projects/ocr-pipeline
export HF_HOME="$REPO/bakeoff/work/hf_cache"
export HUGGINGFACE_HUB_CACHE="$HF_HOME/hub"
export HF_HUB_CACHE="$HF_HOME/hub"
export TRANSFORMERS_CACHE="$HF_HOME/transformers"
mkdir -p "$HF_HOME/hub"
exec "$REPO/bakeoff/.docling-venv/bin/python" -u "$REPO/bakeoff/scripts/run_docling_p1.py"
