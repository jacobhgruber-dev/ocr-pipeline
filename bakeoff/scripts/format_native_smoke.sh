#!/usr/bin/env bash
# Native extract for EPUB/DOCX (no OCR). Requires pandoc.
set -euo pipefail
SAMPLES="${1:-/Users/jacobgruber/Projects/ocr-pipeline/bakeoff/samples}"
OUT="/Users/jacobgruber/Projects/ocr-pipeline/bakeoff/results"
WORK="/Users/jacobgruber/Projects/ocr-pipeline/bakeoff/work/native"
mkdir -p "$OUT" "$WORK"
JSONL="$OUT/format_native.jsonl"
: > "$JSONL"
command -v pandoc >/dev/null || { echo "pandoc missing"; exit 1; }

for f in "$SAMPLES"/*.{epub,docx,html,htm}; do
  [[ -f "$f" ]] || continue
  id=$(basename "$f")
  id_stem="${id%.*}"
  ext="${id##*.}"
  wdir="$WORK/$id_stem"
  mkdir -p "$wdir"
  md="$wdir/out.md"
  t0=$(date +%s)
  case "$ext" in
    epub|docx|html|htm) pandoc "$f" -t markdown -o "$md" 2>"$wdir/pandoc.err" || { echo "FAIL $id"; continue; } ;;
    *) echo "skip $id"; continue ;;
  esac
  t1=$(date +%s)
  chars=$(wc -c < "$md" | tr -d ' ')
  words=$(wc -w < "$md" | tr -d ' ')
  python3 - << PY >> "$JSONL"
import json, time
print(json.dumps({
  "sample_id": "$id_stem",
  "format": "$ext",
  "engine": "pandoc",
  "md_chars": int("${chars:-0}" or 0),
  "md_words": int("${words:-0}" or 0),
  "elapsed_s": int("$((t1-t0))"),
  "route": "format_native_no_ocr",
  "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
  "phase": "P0_native",
}))
PY
  echo "native $id chars=$chars"
done
echo "wrote $JSONL"
