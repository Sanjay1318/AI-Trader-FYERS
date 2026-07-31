from pathlib import Path
from reporting.report_writer import (
    save_validation_summary,
    save_invalid_rows,
    save_issues_report,
)

from validators.common import (
    ValidationResult,
    load_csv,
    basic_info,
    check_missing_values,
    check_duplicate_rows,
    check_date_column,
)

from validators.ohlc_validator import (
    validate_required_columns,
    validate_price_values,
    validate_negative_prices,
    validate_zero_prices,
)

# ==========================================================
# CONFIG
# ==========================================================

DATA_FOLDER = Path(r"E:\AI-trader\market_data\raw\indices")

# ==========================================================
# FIND FILES
# ==========================================================

csv_files = sorted(DATA_FOLDER.glob("*.csv"))

if not csv_files:
    print("❌ No CSV files found.")
    exit()

print("=" * 70)
print("INDEX DATA VALIDATION")
print("=" * 70)

passed = 0
warnings = 0
failed = 0
results = []

# ==========================================================
# VALIDATE
# ==========================================================

for csv_file in csv_files:

    result = ValidationResult()
    result.file_name = csv_file.name

    print(f"\n📄 {csv_file.name}")

    try:

        df = load_csv(csv_file)

        basic_info(df, result)

        validate_required_columns(df, result)

        if result.status == "PASS":

            check_missing_values(df, result)
            check_duplicate_rows(df, result)
            check_date_column(df, result)

            validate_price_values(df, result)
            validate_negative_prices(df, result)
            validate_zero_prices(df, result)

        print(f"Rows                : {result.rows:,}")
        print(f"Columns             : {result.columns}")
        print(f"Date Range          : {result.start_date}  -->  {result.end_date}")
        print(f"Missing Values      : {result.missing_values}")
        print(f"Duplicate Rows      : {result.duplicate_rows}")
        print(f"Duplicate Dates     : {result.duplicate_timestamps}")

        if result.errors:
            print("\nErrors:")
            for err in result.errors:
                print(f"  - {err}")

        if result.invalid_rows:

            print("\nInvalid Rows:")

            for row in result.invalid_rows[:5]:

                print(
                    f"  Row {row['row']} | "
                    f"{row['date']} | "
                    f"{row['issues']}"
                )

            if len(result.invalid_rows) > 5:

                print(
                    f"  ... and {len(result.invalid_rows) - 5} more"
                )

        print(f"\nStatus              : {result.status}")

        if result.severity == "PASS":
            passed += 1

        elif result.severity == "WARNING":
            warnings += 1

        else:
            failed += 1

        results.append(result)

    except Exception as e:

        result.status = "ERROR"
        result.errors.append(str(e))

        results.append(result)

        failed += 1

        print(f"❌ ERROR: {e}")

# ==========================================================
# SUMMARY
# ==========================================================

save_validation_summary(results)
save_invalid_rows(results)

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

print(f"Total Files : {len(csv_files)}")
print(f"Passed      : {passed}")
print(f"Warnings    : {warnings}")
print(f"Failed      : {failed}")

print("=" * 70)

save_validation_summary(results)
save_invalid_rows(results)
save_issues_report(results)