"""
clean_indices.py

Main runner for cleaning all index CSV files.
"""

from pathlib import Path

from cleaners.indices_cleaner import clean_index_file
from reporting.report_writer import (
    write_cleaning_report,
    print_summary,
)


# ==========================================================
# Project Paths
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "market_data" / "raw" / "indices"

OUTPUT_DIR = (
    PROJECT_ROOT
    / "market_data"
    / "validated"
    / "indices"
)

REPORT_DIR = (
    PROJECT_ROOT
    / "data_pipeline"
    / "reports"
    / "cleaning"
)


# ==========================================================
# Main
# ==========================================================

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    csv_files = sorted(
        RAW_DIR.glob("*.csv")
    )

    if not csv_files:
        print(f"\nNo CSV files found in:\n{RAW_DIR}")
        return

    summaries = []

    print("=" * 70)
    print("MARKET DATA CLEANING PIPELINE")
    print("=" * 70)

    print(f"\nInput Folder : {RAW_DIR}")
    print(f"Output Folder: {OUTPUT_DIR}")
    print(f"Files Found  : {len(csv_files)}\n")

    for i, csv_file in enumerate(csv_files, start=1):

        print(f"[{i}/{len(csv_files)}] Cleaning {csv_file.name}")

        output_file = OUTPUT_DIR / csv_file.name

        summary = clean_index_file(
            csv_file,
            output_file
        )

        summaries.append(summary)

        if summary["status"] == "SUCCESS":
            print(
                f"   ✓ "
                f"{summary['original_rows']} -> "
                f"{summary['final_rows']} rows"
            )
        else:
            print(
                f"   ✗ FAILED : {summary['error']}"
            )

    report_file = write_cleaning_report(
        summaries,
        REPORT_DIR,
    )

    print_summary(summaries)

    print("\nCleaning report saved to:")
    print(report_file)

    print("\nCleaning pipeline completed successfully.")


# ==========================================================
# Entry Point
# ==========================================================

if __name__ == "__main__":
    main()