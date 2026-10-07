#!/usr/bin/env python3
"""Merge P0 JSONL smoke results into results/bakeoff_scores.csv skeleton."""
from __future__ import annotations
import csv, json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
CSV_PATH = RES / "bakeoff_scores.csv"
FIELDS = [
    "sample_id", "phase", "format", "engine", "recommended_path", "route",
    "pages_total", "slice_chars", "md_chars", "md_words", "garbage_hits",
    "fonts_type1", "fonts_truetype", "elapsed_s", "footnote_f1", "italics_recall",
    "reflow_rubric", "table_ok", "equation_ok", "callout_ok", "page_map_ok",
    "artifact_residue_mb", "notes", "ts",
]

def load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows

def main() -> None:
    merged: dict[str, dict] = {}
    for name in ("smoke_pdftotext.jsonl", "marker_slice.jsonl", "format_native.jsonl", "image_tesseract.jsonl"):
        for row in load_jsonl(RES / name):
            sid = row.get("sample_id") or "unknown"
            key = f"{sid}|{row.get('phase','')}|{row.get('engine', row.get('recommended_path',''))}"
            base = {
                "sample_id": sid,
                "phase": row.get("phase", ""),
                "format": row.get("format", "pdf" if "pdf" in sid or sid.startswith("S0") else ""),
                "engine": row.get("engine", ""),
                "recommended_path": row.get("recommended_path", ""),
                "route": row.get("route", ""),
                "pages_total": row.get("pages_total", ""),
                "slice_chars": row.get("slice_chars", ""),
                "md_chars": row.get("md_chars", ""),
                "md_words": row.get("md_words", ""),
                "garbage_hits": row.get("garbage_hits", ""),
                "fonts_type1": row.get("fonts_type1", ""),
                "fonts_truetype": row.get("fonts_truetype", ""),
                "elapsed_s": row.get("elapsed_s", ""),
                "footnote_f1": "",
                "italics_recall": "",
                "reflow_rubric": "",
                "table_ok": "",
                "equation_ok": "",
                "callout_ok": "",
                "page_map_ok": "",
                "artifact_residue_mb": "",
                "notes": row.get("mode", row.get("flags", "")),
                "ts": row.get("ts", time.strftime("%Y-%m-%dT%H:%M:%S%z")),
            }
            merged[key] = base
    RES.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for row in sorted(merged.values(), key=lambda r: (r["sample_id"], r["phase"])):
            w.writerow(row)
    print(f"wrote {CSV_PATH} ({len(merged)} rows)")

if __name__ == "__main__":
    main()
