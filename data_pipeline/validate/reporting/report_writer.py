from pathlib import Path
import csv

# ==========================================================
# REPORT CONFIGURATION
# ==========================================================

REPORT_FOLDER = Path(r"E:\AI-trader\data_pipeline\reports\validation")

REPORT_FOLDER.mkdir(parents=True, exist_ok=True)


# ==========================================================
# VALIDATION SUMMARY REPORT
# ==========================================================

def save_validation_summary(results):
    """
    Save one summary row for every validated file.
    """

    output_file = REPORT_FOLDER / "validation_summary.csv"

    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:

        writer = csv.writer(csvfile)

        writer.writerow([
            "File",
            "Rows",
            "Columns",
            "Missing Values",
            "Duplicate Rows",
            "Duplicate Timestamps",
            "Invalid OHLC Rows",
            "Severity"
        ])

        for result in results:

            writer.writerow([
                result.file_name,
                result.rows,
                result.columns,
                result.missing_values,
                result.duplicate_rows,
                result.duplicate_timestamps,
                result.invalid_ohlc_rows,
                result.severity
            ])

    print("\n" + "=" * 70)
    print(f"✅ Validation summary saved:")
    print(output_file)
    print("=" * 70)

def save_invalid_rows(results):
    """
    Save every invalid row from every validated file.
    """

    output_file = REPORT_FOLDER / "invalid_rows.csv"

    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:

        writer = csv.writer(csvfile)

        writer.writerow([
            "File",
            "CSV Row",
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
            "Issue"
        ])

        for result in results:

            for row in result.invalid_rows:

                writer.writerow([
                    result.file_name,
                    row["row"],
                    row["date"],
                    row["open"],
                    row["high"],
                    row["low"],
                    row["close"],
                    row["issues"]
                ])

    print("\n" + "=" * 70)
    print("✅ Invalid rows report saved:")
    print(output_file)
    print("=" * 70)

def save_issues_report(results):
    """
    Save all WARNING and FAIL files.
    """

    output_file = REPORT_FOLDER / "issues.csv"

    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:

        writer = csv.writer(csvfile)

        writer.writerow([
            "File",
            "Severity",
            "Rows",
            "Missing Values",
            "Duplicate Rows",
            "Duplicate Dates",
            "Invalid OHLC Rows",
            "Errors"
        ])

        for result in results:

            if result.severity == "PASS":
                continue

            writer.writerow([
                result.file_name,
                result.severity,
                result.rows,
                result.missing_values,
                result.duplicate_rows,
                result.duplicate_timestamps,
                result.invalid_ohlc_rows,
                " | ".join(result.errors)
            ])

    print("\n" + "=" * 70)
    print("✅ Issues report saved:")
    print(output_file)
    print("=" * 70)