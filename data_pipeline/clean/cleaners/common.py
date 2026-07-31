"""
common.py

Reusable data cleaning utilities for market datasets.
"""

from pathlib import Path
import pandas as pd


# ==========================================================
# File Handling
# ==========================================================

def load_csv(file_path: str | Path) -> pd.DataFrame:
    """
    Load a CSV file into a DataFrame.
    """
    return pd.read_csv(file_path)


def save_csv(df: pd.DataFrame, output_path: str | Path):
    """
    Save DataFrame to CSV.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(output_path, index=False)


# ==========================================================
# Timestamp Handling
# ==========================================================

def standardize_datetime(df):
    """
    Automatically detect and standardize the datetime column.
    """

    candidates = [
        "timestamp",
        "Timestamp",
        "datetime",
        "Datetime",
        "date",
        "Date",
        "DATE"
    ]

    timestamp_column = None

    for col in candidates:
        if col in df.columns:
            timestamp_column = col
            break

    if timestamp_column is None:
        raise ValueError(
            "No timestamp/date column found."
        )

    df[timestamp_column] = pd.to_datetime(
        df[timestamp_column],
        errors="coerce"
    )

    return df, timestamp_column


def remove_invalid_timestamps(df, timestamp_column):
    before = len(df)

    df = df.dropna(subset=[timestamp_column])

    removed = before - len(df)

    return df, removed


def sort_by_timestamp(df, timestamp_column):
    return df.sort_values(timestamp_column)


# ==========================================================
# Duplicate Removal
# ==========================================================

def remove_duplicate_rows(df: pd.DataFrame):
    """
    Remove exact duplicate rows.
    """

    before = len(df)

    df = df.drop_duplicates()

    removed = before - len(df)

    return df, removed


def remove_duplicate_timestamps(
    df: pd.DataFrame,
    timestamp_column: str
):
    """
    Keep first occurrence of duplicate timestamps.
    """

    before = len(df)

    df = df.drop_duplicates(
        subset=[timestamp_column],
        keep="first"
    )

    removed = before - len(df)

    return df, removed


# ==========================================================
# OHLC Validation
# ==========================================================

def remove_invalid_ohlc(df: pd.DataFrame):
    """
    Remove rows with invalid OHLC values.
    Automatically detects column names.
    """

    cols = {c.lower(): c for c in df.columns}

    required = ["open", "high", "low", "close"]

    missing = [c for c in required if c not in cols]

    if missing:
        raise ValueError(f"Missing OHLC columns: {missing}")

    open_col = cols["open"]
    high_col = cols["high"]
    low_col = cols["low"]
    close_col = cols["close"]

    before = len(df)

    df = df[
        (df[high_col] >= df[open_col]) &
        (df[high_col] >= df[close_col]) &
        (df[high_col] >= df[low_col]) &
        (df[low_col] <= df[open_col]) &
        (df[low_col] <= df[close_col]) &
        (df[low_col] <= df[high_col])
    ]

    removed = before - len(df)

    return df, removed

# ==========================================================
# Missing Values
# ==========================================================

def remove_missing_rows(df: pd.DataFrame):
    """
    Remove rows containing missing values.
    """

    before = len(df)

    df = df.dropna()

    removed = before - len(df)

    return df, removed

# ==========================================================
# Final Cleanup
# ==========================================================

def reset_dataframe(df: pd.DataFrame):
    """
    Reset DataFrame index.
    """

    return df.reset_index(drop=True)


# ==========================================================
# Statistics
# ==========================================================

def dataframe_stats(df: pd.DataFrame):
    """
    Return basic dataframe statistics.
    """

    return {
        "rows": len(df),
        "columns": len(df.columns),
        "memory_mb": round(
            df.memory_usage(deep=True).sum() / 1024 / 1024,
            2
        )
    }