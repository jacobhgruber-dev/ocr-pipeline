#!/usr/bin/env bash
# Cheap PDF smoke: pdffonts + pdftotext page slice → results/smoke_pdftotext.jsonl
set -euo pipefail
SAMPLES="${1:-/Users/jacobgruber/Projects/ocr-pipeline/bakeoff/samples}"
OUT="/Users/jacobgruber/Projects/ocr-pipeline/bakeoff/results"
WORK="/Users/jacobgruber/Projects/ocr-pipeline/bakeoff/work/smoke"
mkdir -p "$OUT" "$WORK"
JSONL="$OUT/smoke_pdftotext.jsonl"
: > "$JSONL"

count_pat() { # file pattern → int (never empty)
  local n
  n=$(grep -cE "$2" "$1" 2>/dev/null || true)
  echo "${n:-0}"
}

for pdf in "$SAMPLES"/*.pdf; do
  [[ -f "$pdf" ]] || continue
  id=$(basename "$pdf" .pdf)
  wdir="$WORK/$id"
  mkdir -p "$wdir"
  fonts_out="$wdir/pdffonts.txt"
  text_out="$wdir/slice.txt"
  pdffonts "$pdf" > "$fonts_out" 2>&1 || true
  pdftotext -f 1 -l 5 -layout "$pdf" "$text_out" 2>"$wdir/pdftotext.err" || true
  pages=$(pdfinfo "$pdf" 2>/dev/null | awk '/^Pages:/ {print $2}')
  encrypted=$(pdfinfo "$pdf" 2>/dev/null | awk '/^Encrypted:/ {print $2}')
  has_type1=$(count_pat "$fonts_out" 'Type 1')
  has_truetype=$(count_pat "$fonts_out" 'TrueType')
  has_cid=$(count_pat "$fonts_out" 'CID')
  chars=$(wc -c < "$text_out" 2>/dev/null | tr -d ' ' || echo 0)
  words=$(wc -w < "$text_out" 2>/dev/null | tr -d ' ' || echo 0)
  garbage=$(grep -cE '[A-Za-z]*[~`][A-Za-z]*|tha~|phoemx|Histaria|raIse|AlIsgabe' "$text_out" 2>/dev/null || true)
  garbage=${garbage:-0}
  replacement=$(python3 -c "print(open('$text_out','rb').read().count(b'\\xef\\xbf\\xbd'))" 2>/dev/null || echo 0)
  if [[ "${chars:-0}" -gt 500 && ( "${has_type1:-0}" -gt 0 || "${has_truetype:-0}" -gt 0 ) ]]; then
    path="marker_disable_ocr"
  elif [[ "${chars:-0}" -lt 100 ]]; then
    path="image_or_scan_ocr"
  else
    path="hybrid_check"
  fi
  python3 -c "
import json, time
print(json.dumps({
  'sample_id': '$id',
  'file': '$pdf',
  'pages_total': int('${pages or 0}' or 0),
  'encrypted': '${encrypted}',
  'fonts_type1': int('$has_type1' or 0),
  'fonts_truetype': int('$has_truetype' or 0),
  'fonts_cid': int('$has_cid' or 0),
  'slice_chars': int('${chars or 0}' or 0),
  'slice_words': int('${words or 0}' or 0),
  'garbage_hits': int('$garbage' or 0),
  'replacement_chars': int('${replacement or 0}' or 0),
  'recommended_path': '$path',
  'ts': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
  'phase': 'P0_smoke',
}))
" >> "$JSONL"
  echo "smoke $id pages=$pages chars=$chars path=$path garbage=$garbage"
done
echo "wrote $JSONL"
