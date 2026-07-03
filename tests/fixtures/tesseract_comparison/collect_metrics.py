"""Collect metrics from tesseract comparison study runs."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

# Base paths
BASE = Path("/Users/jacobgruber/Projects/ocr-pipeline")
COMP = BASE / "tests/fixtures/tesseract_comparison"
FIXTURES = BASE / "tests/fixtures"

# Script profile mapping
SCRIPT_MAP = {
    "academic": "Latin (English)",
    "books": "Latin (English)",
    "legal": "Latin (English)",
    "technical": "Latin (English)",
    "french": "Latin+diacritics",
    "russian": "Cyrillic",
    "chinese": "CJK",
    "arabic": "Arabic",
}

# Profile for each test dir
PROFILE_MAP = {
    "academic": "academic",
    "books": "books",
    "legal": "legal",
    "technical": "technical",
    "french": "books",
    "russian": "mathematical",
    "chinese": "academic",
    "arabic": "general",
}


def has_non_latin(text: str) -> float:
    """Return ratio of non-Latin characters."""
    if not text:
        return 0.0
    non_latin = sum(1 for c in text if ord(c) > 127)
    return non_latin / max(len(text), 1)


def has_script(text: str, script_name: str) -> bool:
    """Check if expected script characters appear in text."""
    ranges = {
        "Cyrillic": [(0x0400, 0x04FF)],
        "CJK": [(0x4E00, 0x9FFF), (0x3400, 0x4DBF)],
        "Arabic": [(0x0600, 0x06FF), (0x0750, 0x077F)],
        "Latin_diacritics": [(0x00C0, 0x00FF)],  # Latin-1 Supplement
    }
    if script_name not in ranges:
        return False
    for lo, hi in ranges[script_name]:
        if any(lo <= ord(c) <= hi for c in text):
            return True
    return False


def normalize_for_cer(text: str) -> str:
    """Normalize text for CER comparison."""
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def cer(ref: str, hyp: str) -> float:
    """Character Error Rate using edit distance."""
    try:
        import editdistance
        d = editdistance.eval(ref, hyp)
        return d / max(len(ref), len(hyp), 1)
    except ImportError:
        # Fallback: simple Levenshtein-like check
        # Use a rough heuristic
        import difflib
        s = difflib.SequenceMatcher(None, ref, hyp)
        return 1.0 - s.ratio()


def find_baseline(profile: str, pdf_hash: str) -> Path | None:
    """Find existing marker baseline for comparison."""
    # English profiles have baseline in tests/fixtures/{profile}/output/{hash}/
    candidates = [
        FIXTURES / profile / "output" / pdf_hash,
    ]

    # Multilingual baselines
    lang_baselines = {
        "french": FIXTURES / "multilingual" / "output_french_books",
        "russian": FIXTURES / "multilingual" / "output_russian_best",
        "chinese": FIXTURES / "multilingual" / "output_chinese_cheap",
    }
    if profile in lang_baselines:
        candidates.append(lang_baselines[profile])

    for cand in candidates:
        md = cand / "page_0001_final.md"
        if md.exists():
            return md.parent
    return None


def main() -> None:
    rows = []

    for config in ["T-G", "MT-G"]:
        for profile in ["academic", "books", "legal", "technical",
                         "french", "russian", "chinese", "arabic"]:
            out_dir = COMP / config / profile
            if not out_dir.exists():
                continue

            # Find all page final.md files
            for md_file in sorted(out_dir.rglob("page_*_final.md")):
                pdf_hash = md_file.parent.name
                page_name = md_file.stem  # e.g., page_0001_final

                # Load final markdown
                md_text = md_file.read_text(encoding="utf-8")

                # Strip HTML comment header
                md_body = md_text
                if md_body.startswith("<!--"):
                    end = md_body.find("-->")
                    if end > 0:
                        md_body = md_body[end + 3:].strip()

                char_count = len(md_body)
                word_count = len(md_body.split()) if md_body.strip() else 0
                non_latin = has_non_latin(md_body)
                nl_ratio = round(non_latin, 4)

                # Script-specific checks
                script = SCRIPT_MAP.get(profile, "Unknown")
                cyrillic = has_script(md_body, "Cyrillic")
                cjk = has_script(md_body, "CJK")
                arabic = has_script(md_body, "Arabic")
                diacritics = has_script(md_body, "Latin_diacritics")

                # Load raw.json for metadata
                raw_file = md_file.parent / f"{page_name.replace('_final', '')}_raw.json"
                agreement = 0.0
                engine_count = 0
                if raw_file.exists():
                    try:
                        raw = json.loads(raw_file.read_text(encoding="utf-8"))
                        agreement = raw.get("engines_agreement", 0.0)
                        engine_outputs = raw.get("engine_outputs", {})
                        engine_count = len(engine_outputs)
                    except (json.JSONDecodeError, KeyError):
                        pass

                # Cross-CER against marker baseline
                baseline_dir = find_baseline(PROFILE_MAP.get(profile, profile), pdf_hash)
                baseline_cer = None
                if baseline_dir:
                    base_md = baseline_dir / f"{page_name}.md"  # _final already in name
                    if base_md.exists():
                        base_text = base_md.read_text(encoding="utf-8")
                        # Strip HTML comment header from baseline too
                        base_body = base_text
                        if base_body.startswith("<!--"):
                            end = base_body.find("-->")
                            if end > 0:
                                base_body = base_body[end + 3:].strip()
                        norm_ref = normalize_for_cer(base_body)
                        norm_hyp = normalize_for_cer(md_body)
                        baseline_cer = round(cer(norm_ref, norm_hyp), 4)

                rows.append({
                    "config": config,
                    "profile": profile,
                    "script": script,
                    "pdf_hash": pdf_hash,
                    "page": page_name,
                    "char_count": char_count,
                    "word_count": word_count,
                    "non_latin_ratio": nl_ratio,
                    "cyrillic_found": cyrillic,
                    "cjk_found": cjk,
                    "arabic_found": arabic,
                    "diacritics_found": diacritics,
                    "engines_agreement": round(agreement, 4),
                    "engine_count": engine_count,
                    "cross_cer_vs_baseline": baseline_cer,
                })

    # Print summary table
    print("\n=== PER-PAGE METRICS ===")
    print(f"{'Config':<6} {'Profile':<12} {'Script':<20} {'Page':<16} {'Chars':>8} {'Words':>8} {'NonLatin':>8} {'Cyr':>4} {'CJK':>4} {'Ar':>3} {'Dia':>4} {'Agree':>6} {'CERvsBL':>8}")
    print("-" * 130)
    for r in rows:
        cyr = "✅" if r["cyrillic_found"] else "  "
        cj = "✅" if r["cjk_found"] else "  "
        ar = "✅" if r["arabic_found"] else "  "
        dia = "✅" if r["diacritics_found"] else "  "
        cer_str = f"{r['cross_cer_vs_baseline']:.2%}" if r["cross_cer_vs_baseline"] is not None else "N/A"
        print(f"{r['config']:<6} {r['profile']:<12} {r['script']:<20} {r['page']:<16} {r['char_count']:>8} {r['word_count']:>8} {r['non_latin_ratio']:>8.2%} {cyr:>4} {cj:>4} {ar:>3} {dia:>4} {r['engines_agreement']:>6.1%} {cer_str:>8}")

    # Aggregate by script + config
    print("\n\n=== PER-SCRIPT SUMMARY ===")
    print(f"{'Script':<22} {'Config':<6} {'Pages':>6} {'Avg Chars':>10} {'Avg Words':>9} {'Avg NonLatin':>10}")
    print("-" * 70)

    from collections import defaultdict
    agg = defaultdict(lambda: {"chars": 0, "words": 0, "non_latin": 0, "pages": 0, "cers": []})
    for r in rows:
        key = (r["script"], r["config"])
        agg[key]["chars"] += r["char_count"]
        agg[key]["words"] += r["word_count"]
        agg[key]["non_latin"] += r["non_latin_ratio"]
        agg[key]["pages"] += 1
        if r["cross_cer_vs_baseline"] is not None:
            agg[key]["cers"].append(r["cross_cer_vs_baseline"])

    for (script, config), vals in sorted(agg.items()):
        n = vals["pages"]
        avg_cer = sum(vals["cers"]) / len(vals["cers"]) if vals["cers"] else None
        cer_str = f"{avg_cer:.2%}" if avg_cer is not None else "N/A"
        print(f"{script:<22} {config:<6} {n:>6} {vals['chars']/n:>10.0f} {vals['words']/n:>9.0f} {vals['non_latin']/n:>9.1%}  CER={cer_str}")

    # Write CSV
    csv_path = COMP / "metrics.csv"
    if rows:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nCSV written to {csv_path}")


if __name__ == "__main__":
    main()
