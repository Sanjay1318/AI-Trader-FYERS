"""
indices_cleaner.py

Cleans a single indices CSV file using reusable functions from common.py.
"""

from pathlib import Path

from .common import (
    load_csv,
    save_csv,
    standardize_datetime,
    remove_invalid_timestamps,
    remove_duplicate_rows,
    remove_duplicate_timestamps,
    sort_by_timestamp,
    remove_invalid_ohlc,
    remove_missing_rows,
    reset_dataframe,
    dataframe_stats,
)


def clean_index_file(input_file: str | Path, output_file: str | Path):
    """
    Clean a single index CSV file.

    Returns
    -------
    dict
        Cleaning statistics.
    """

    input_file = Path(input_file)
    output_file = Path(output_file)

    summary = {
        "file": input_file.name,
        "status": "SUCCESS",
        "original_rows": 0,
        "final_rows": 0,
        "duplicates_removed": 0,
        "duplicate_timestamps_removed": 0,
        "invalid_timestamp_removed": 0,
        "invalid_ohlc_removed": 0,
        "missing_rows_removed": 0,
        "error": "",
    }

    try:

        # -------------------------------------------------
        # Load CSV
        # -------------------------------------------------

        df = load_csv(input_file)

        summary["original_rows"] = len(df)

                # -------------------------------------------------
        # Standardize datetime
        # -------------------------------------------------

        df, timestamp_column = standardize_datetime(df)

        # -------------------------------------------------
        # Remove invalid timestamps
        # -------------------------------------------------

        df, removed = remove_invalid_timestamps(
            df,
            timestamp_column
        )

        summary["invalid_timestamp_removed"] = removed

        # -------------------------------------------------
        # Remove duplicate rows
        # -------------------------------------------------

        df, removed = remove_duplicate_rows(df)

        summary["duplicates_removed"] = removed

        # -------------------------------------------------
        # Remove duplicate timestamps
        # -------------------------------------------------

        df, removed = remove_duplicate_timestamps(
            df,
            timestamp_column
        )

        summary["duplicate_timestamps_removed"] = removed

        # -------------------------------------------------
        # Sort timestamps
        # -------------------------------------------------

        df = sort_by_timestamp(
            df,
            timestamp_column
        )

        # -------------------------------------------------
        # Remove invalid OHLC
        # -------------------------------------------------

        df, removed = remove_invalid_ohlc(df)

        summary["invalid_ohlc_removed"] = removed

        # -------------------------------------------------
        # Remove missing values
        # -------------------------------------------------

        df, removed = remove_missing_rows(df)

        summary["missing_rows_removed"] = removed

        # -------------------------------------------------
        # Reset index
        # -------------------------------------------------

        df = reset_dataframe(df)

        summary["final_rows"] = len(df)

        # -------------------------------------------------
        # Save cleaned CSV
        # -------------------------------------------------

        save_csv(df, output_file)

        stats = dataframe_stats(df)

        summary["rows"] = stats["rows"]
        summary["columns"] = stats["columns"]
        summary["memory_mb"] = stats["memory_mb"]

    except Exception as e:

        summary["status"] = "FAILED"
        summary["error"] = str(e)

    return summary