"""
report_writer.py

Generates cleaning summary reports.
"""

from pathlib import Path
import pandas as pd


def write_cleaning_report(
    summaries,
    report_dir
):
    """
    Generate cleaning_summary.csv

    Parameters
    ----------
    summaries : list
        List of dictionaries returned by clean_index_file()

    report_dir : str | Path
        Directory to save report.
    """

    report_dir = Path(report_dir)
    report_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    df = pd.DataFrame(summaries)

    columns = [
        "file",
        "status",
        "original_rows",
        "final_rows",
        "duplicates_removed",
        "duplicate_timestamps_removed",
        "invalid_timestamp_removed",
        "invalid_ohlc_removed",
        "missing_rows_removed",
        "rows",
        "columns",
        "memory_mb",
        "error"
    ]

    for col in columns:
        if col not in df.columns:
            df[col] = ""

    df = df[columns]

    report_file = report_dir / "cleaning_summary.csv"

    df.to_csv(
        report_file,
        index=False
    )

    return report_file


def print_summary(
    summaries
):
    """
    Print cleaning summary.
    """

    total_files = len(summaries)

    successful = sum(
        1
        for s in summaries
        if s["status"] == "SUCCESS"
    )

    failed = total_files - successful

    original_rows = sum(
        s.get("original_rows", 0)
        for s in summaries
    )

    final_rows = sum(
        s.get("final_rows", 0)
        for s in summaries
    )

    duplicates = sum(
        s.get("duplicates_removed", 0)
        for s in summaries
    )

    duplicate_ts = sum(
        s.get("duplicate_timestamps_removed", 0)
        for s in summaries
    )

    invalid_ts = sum(
        s.get("invalid_timestamp_removed", 0)
        for s in summaries
    )

    invalid_ohlc = sum(
        s.get("invalid_ohlc_removed", 0)
        for s in summaries
    )

    missing = sum(
        s.get("missing_rows_removed", 0)
        for s in summaries
    )

    print("\n" + "=" * 60)
    print("DATA CLEANING SUMMARY")
    print("=" * 60)

    print(f"Total Files               : {total_files}")
    print(f"Successful                : {successful}")
    print(f"Failed                    : {failed}")

    print("-" * 60)

    print(f"Original Rows             : {original_rows:,}")
    print(f"Final Rows                : {final_rows:,}")

    print("-" * 60)

    print(f"Duplicate Rows Removed    : {duplicates:,}")
    print(f"Duplicate Timestamps      : {duplicate_ts:,}")
    print(f"Invalid Timestamps        : {invalid_ts:,}")
    print(f"Invalid OHLC Rows         : {invalid_ohlc:,}")
    print(f"Missing Value Rows        : {missing:,}")

    print("=" * 60)