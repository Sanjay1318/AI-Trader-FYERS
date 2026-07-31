"""
Feature Engineering Report Writer

Generates summary reports after feature engineering.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd


def generate_feature_report(
    input_df: pd.DataFrame,
    output_df: pd.DataFrame,
    output_dir: str | Path,
    filename: str = "feature_engineering_summary.csv",
) -> pd.DataFrame:
    """
    Generate a feature engineering summary report.

    Parameters
    ----------
    input_df : pd.DataFrame
        Original cleaned dataframe.
    output_df : pd.DataFrame
        Feature engineered dataframe.
    output_dir : str | Path
        Directory where the report will be saved.
    filename : str
        Report filename.

    Returns
    -------
    pd.DataFrame
        Summary dataframe.
    """

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "input_rows": len(input_df),
        "output_rows": len(output_df),
        "input_columns": len(input_df.columns),
        "output_columns": len(output_df.columns),
        "new_features": len(output_df.columns) - len(input_df.columns),
        "missing_values": int(output_df.isna().sum().sum()),
        "duplicate_rows": int(output_df.duplicated().sum()),
    }

    report = pd.DataFrame([summary])

    report.to_csv(
        output_dir / filename,
        index=False,
    )

    return report