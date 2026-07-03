"""OCR Pipeline benchmark — compares pipeline output against ground truth.

Reads ground truth text files from ``tests/fixtures/ground_truth/``, finds
the corresponding ``page_0001_final.md`` output in each profile's output
directory, and computes CER/WER via ``ocr_pipeline.accuracy``.

Usage::

    uv run python scripts/benchmark.py
"""

from __future__ import annotations

import csv
from pathlib import Path

from ocr_pipeline.accuracy import evaluate

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"
GROUND_TRUTH = FIXTURES / "ground_truth"
RESULTS_CSV = FIXTURES / "benchmark_results.csv"

# Map ground truth file names → (profile, hash_dir)
# The hash dirs correspond to the output directories under
# tests/fixtures/{profile}/output/{hash}/
GT_MAPPING: dict[str, tuple[str, str]] = {
    "academic_title_abstract.txt": ("academic", "465516bfd9b6"),
    "academic_citations_body.txt": ("academic", "d28ae549466c"),
    "mathematical_theorem_proof.txt": ("mathematical", "a4b5352e0b0d"),
    "mathematical_lemma_proof.txt": ("mathematical", "3c40f4f45188"),
    "legal_court_opinion.txt": ("legal", "310b6cbe94a1"),
    "legal_section_hierarchy.txt": ("legal", "f7f0579e415a"),
    "technical_datasheet_specs.txt": ("technical", "94c7628f56b5"),
    "technical_pin_config.txt": ("technical", "c0d18778a95b"),
    "books_block_quotes.txt": ("books", "3a3cbe6e92dc"),
    "books_chapter_opening.txt": ("books", "8fcc93a5caa5"),
    "general_periodic_table.txt": ("general", "58a0ffa1826a"),
    "general_mixed_format.txt": ("general", "b5e22dce81a2"),
}


def collect_results() -> list[dict]:
    """Evaluate all ground truth files against their corresponding outputs."""
    results: list[dict] = []
    for gt_name, (profile, hash_dir) in sorted(GT_MAPPING.items()):
        gt_path = GROUND_TRUTH / gt_name
        hyp_path = FIXTURES / profile / "output" / hash_dir / "page_0001_final.md"

        if not gt_path.exists():
            print(f"  [WARN] Ground truth missing: {gt_path}")
            continue
        if not hyp_path.exists():
            print(f"  [WARN] Output missing: {hyp_path}")
            continue

        metrics = evaluate(gt_path, hyp_path, normalized=True)
        fixture_name = gt_name.replace(".txt", "")
        results.append(
            {
                "profile": profile,
                "fixture": fixture_name,
                "cer": metrics["cer"],
                "wer": metrics["wer"],
                "ref_chars": metrics["ref_chars"],
                "hyp_chars": metrics["hyp_chars"],
            }
        )
    return results


def print_table(results: list[dict]) -> None:
    """Print a formatted results table."""
    header_fmt = "{:<14} {:<36} {:>8} {:>8} {:>8} {:>8}"
    row_fmt = "{:<14} {:<36} {:>7.2%} {:>7.2%} {:>8} {:>8}"

    print("\n=== OCR BENCHMARK RESULTS ===\n")
    print(header_fmt.format("Profile", "Fixture", "CER", "WER", "Ref Ch", "Hyp Ch"))
    print("-" * 86)

    for r in results:
        print(
            row_fmt.format(
                r["profile"],
                r["fixture"],
                r["cer"],
                r["wer"],
                r["ref_chars"],
                r["hyp_chars"],
            )
        )

    # Summary per profile
    print("\n=== PER-PROFILE SUMMARY ===\n")
    summary_fmt = "{:<14} {:>5} {:>8} {:>8}"
    print(summary_fmt.format("Profile", "Count", "Avg CER", "Avg WER"))
    print("-" * 41)

    from collections import defaultdict

    by_profile: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_profile[r["profile"]].append(r)

    all_cers: list[float] = []
    all_wers: list[float] = []
    for profile in sorted(by_profile):
        items = by_profile[profile]
        avg_cer = sum(r["cer"] for r in items) / len(items)
        avg_wer = sum(r["wer"] for r in items) / len(items)
        all_cers.extend(r["cer"] for r in items)
        all_wers.extend(r["wer"] for r in items)
        print(summary_fmt.format(profile, len(items), f"{avg_cer:.2%}", f"{avg_wer:.2%}"))

    if all_cers:
        print("-" * 41)
        print(
            summary_fmt.format(
                "OVERALL",
                len(all_cers),
                f"{sum(all_cers) / len(all_cers):.2%}",
                f"{sum(all_wers) / len(all_wers):.2%}",
            )
        )

    print()


def write_csv(results: list[dict]) -> None:
    """Write results to CSV."""
    if not results:
        return
    fieldnames = ["profile", "fixture", "cer", "wer", "ref_chars", "hyp_chars"]
    with open(RESULTS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"CSV report written to {RESULTS_CSV}")


def main() -> None:
    print(f"Ground truth directory: {GROUND_TRUTH}")
    print(f"Evaluating {len(GT_MAPPING)} fixtures...")
    results = collect_results()
    if not results:
        print("No results to report.")
        return
    print_table(results)
    write_csv(results)


if __name__ == "__main__":
    main()
