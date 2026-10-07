#!/usr/bin/env python3
"""Cheap PDF smoke: pdffonts + pdftotext pages 1-5 → results/smoke_pdftotext.jsonl"""
from __future__ import annotations
import json, re, subprocess, time
from pathlib import Path

SAMPLES = Path("/Users/jacobgruber/Projects/ocr-pipeline/bakeoff/samples")
OUT = Path("/Users/jacobgruber/Projects/ocr-pipeline/bakeoff/results")
WORK = Path("/Users/jacobgruber/Projects/ocr-pipeline/bakeoff/work/smoke")
OUT.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)
JSONL = OUT / "smoke_pdftotext.jsonl"

GARBAGE_RE = re.compile(r"[A-Za-z]*[~`][A-Za-z]*|tha~|phoemx|Histaria|raIse|AlIsgabe")

def run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, errors="replace")
    except subprocess.CalledProcessError as e:
        return e.output or ""

rows = []
for pdf in sorted(SAMPLES.glob("*.pdf")):
    sid = pdf.stem
    wdir = WORK / sid
    wdir.mkdir(parents=True, exist_ok=True)
    fonts = run(["pdffonts", str(pdf)])
    (wdir / "pdffonts.txt").write_text(fonts, encoding="utf-8", errors="replace")
    slice_path = wdir / "slice.txt"
    run(["pdftotext", "-f", "1", "-l", "5", "-layout", str(pdf), str(slice_path)])
    text = slice_path.read_text(encoding="utf-8", errors="replace") if slice_path.exists() else ""
    info = run(["pdfinfo", str(pdf)])
    pages = 0
    encrypted = ""
    for line in info.splitlines():
        if line.startswith("Pages:"):
            pages = int(line.split(":",1)[1].strip() or 0)
        if line.startswith("Encrypted:"):
            encrypted = line.split(":",1)[1].strip()
    type1 = fonts.count("Type 1")
    truetype = fonts.count("TrueType")
    cid = fonts.count("CID")
    garbage = len(GARBAGE_RE.findall(text))
    replacement = text.count("\ufffd")
    chars, words = len(text), len(text.split())
    if chars > 500 and (type1 or truetype):
        path = "marker_disable_ocr"
    elif chars < 100:
        path = "image_or_scan_ocr"
    else:
        path = "hybrid_check"
    row = {
        "sample_id": sid,
        "file": str(pdf),
        "pages_total": pages,
        "encrypted": encrypted,
        "fonts_type1": type1,
        "fonts_truetype": truetype,
        "fonts_cid": cid,
        "slice_chars": chars,
        "slice_words": words,
        "garbage_hits": garbage,
        "replacement_chars": replacement,
        "recommended_path": path,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "phase": "P0_smoke",
    }
    rows.append(row)
    print(f"smoke {sid} pages={pages} chars={chars} path={path} garbage={garbage}")

JSONL.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
print("wrote", JSONL, len(rows), "rows")
