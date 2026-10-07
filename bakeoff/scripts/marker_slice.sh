#!/usr/bin/env bash
# Marker --disable_ocr on page slice (default 0-4 = first 5 pages). Tiny PDFs: full.
set -euo pipefail
SAMPLES="${1:-/Users/jacobgruber/Projects/ocr-pipeline/bakeoff/samples}"
MARKER="/Users/jacobgruber/Projects/ocr-pipeline/.marker-venv/bin/marker_single"
OUT="/Users/jacobgruber/Projects/ocr-pipeline/bakeoff/results"
WORK="/Users/jacobgruber/Projects/ocr-pipeline/bakeoff/work/marker"
mkdir -p "$OUT" "$WORK"
JSONL="$OUT/marker_slice.jsonl"
: > "$JSONL"
PAGE_RANGE="${PAGE_RANGE:-0-4}"

for pdf in "$SAMPLES"/*.pdf; do
  [[ -f "$pdf" ]] || continue
  id=$(basename "$pdf" .pdf)
  pages=$(pdfinfo "$pdf" 2>/dev/null | awk '/^Pages:/ {print $2}')
  # full convert if tiny (<=25 pages)
  if [[ "${pages:-999}" -le 25 ]]; then
    range_args=()
    mode="full"
  else
    range_args=(--page_range "$PAGE_RANGE")
    mode="slice:$PAGE_RANGE"
  fi
  wdir="$WORK/$id"
  rm -rf "$wdir"
  mkdir -p "$wdir"
  t0=$(date +%s)
  "$MARKER" "$pdf" \
    --disable_ocr \
    --disable_image_extraction \
    --paginate_output \
    --output_dir "$wdir" \
    "${range_args[@]}" \
    > "$wdir/marker.log" 2>&1 || { echo "FAIL $id"; continue; }
  t1=$(date +%s)
  md=$(find "$wdir" -name '*.md' | head -1)
  chars=0; words=0
  if [[ -n "$md" && -f "$md" ]]; then
    chars=$(wc -c < "$md" | tr -d ' ')
    words=$(wc -w < "$md" | tr -d ' ')
    # strip any accidental images
    find "$wdir" \( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.webp' \) -delete
  fi
  elapsed=$((t1-t0))
  python3 - << PY >> "$JSONL"
import json, time
print(json.dumps({
  "sample_id": "$id",
  "engine": "marker_single",
  "flags": "--disable_ocr --disable_image_extraction --paginate_output",
  "mode": "$mode",
  "pages_total": int("${pages:-0}" or 0),
  "md_path": "$md",
  "md_chars": int("${chars:-0}" or 0),
  "md_words": int("${words:-0}" or 0),
  "elapsed_s": int("$elapsed"),
  "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
  "phase": "P0_marker_slice",
}))
PY
  echo "marker $id mode=$mode elapsed=${elapsed}s chars=$chars"
done
echo "wrote $JSONL"
