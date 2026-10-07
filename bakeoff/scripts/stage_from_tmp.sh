#!/usr/bin/env bash
# Stage finished downloads from /tmp/ocr-bakeoff-dl into AR + repo samples symlink tree.
set -euo pipefail
SRC="${1:-/tmp/ocr-bakeoff-dl}"
AR_SAMPLES="/Users/jacobgruber/Projects/Academic Research/data/jstor_md/bakeoff/samples"
REPO_SAMPLES="/Users/jacobgruber/Projects/ocr-pipeline/bakeoff/samples"
mkdir -p "$AR_SAMPLES" "$REPO_SAMPLES"

# Stable short names
declare -A MAP=(
  ["John Chrysostom — On Repentance and Almsgiving (FOTC 96, 1998).pdf"]="S01_fotc96_chrysostom_repentance.pdf"
)

stage_one() {
  local src="$1" dest_name="$2"
  local ar_dest="$AR_SAMPLES/$dest_name"
  cp -n "$src" "$ar_dest" 2>/dev/null || cp "$src" "$ar_dest"
  ln -sfn "$ar_dest" "$REPO_SAMPLES/$dest_name"
  shasum -a 256 "$ar_dest" | awk '{print $1}' > "${ar_dest}.sha256"
  echo "staged $dest_name ($(du -h "$ar_dest" | cut -f1))"
}

# Walk completed (non-partial) files
while IFS= read -r -d '' f; do
  base=$(basename "$f")
  [[ "$base" == *.partial ]] && continue
  case "$base" in
    *FOTC\ 96*) dest="S01_fotc96_chrysostom_repentance.pdf" ;;
    *Christ\ Party*) dest="S02_sbl_baur_christ_party.pdf" ;;
    *Ethiopic\ Manuscript*|*Catalogue\ of\ the\ Ethiopic*) dest="S07_haile_emip_catalogue1.pdf" ;;
    *Sklaverei*) dest="S10_schlueter_sklaverei_de.pdf" ;;
    *Hymns\ on\ Faith*) dest="S08_fotc130_ephraem_hymns.pdf" ;;
    *Seducing\ Augustine*) dest="S12_burrus_seducing_augustine.pdf" ;;
    *Evening\ Prayer*) dest="S14_evening_prayer_booklet.docx" ;;
    *Archangel\ Gabriel*) dest="S14b_archangel_gabriel.docx" ;;
    *Abbey\ Psalms*) dest="S13_abbey_psalms_canticles.epub" ;;
    *Everyday\ Catholic*) dest="S13b_everyday_loth.epub" ;;
    *) dest="misc_${base// /_}" ;;
  esac
  stage_one "$f" "$dest"
done < <(find "$SRC" -type f ! -name '*.partial' -print0)

echo "AR samples:"; ls -lah "$AR_SAMPLES"
