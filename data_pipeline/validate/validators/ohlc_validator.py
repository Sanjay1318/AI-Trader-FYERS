from .common import ValidationResult


REQUIRED_COLUMNS = [
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume"
]


def validate_required_columns(df, result: ValidationResult):
    """
    Ensure all required OHLC columns exist.
    """

    missing = []

    for column in REQUIRED_COLUMNS:
        if column not in df.columns:
            missing.append(column)

    if missing:
        result.status = "FAIL"
        result.errors.append(
            f"Missing columns: {', '.join(missing)}"
        )


def validate_price_values(df, result: ValidationResult):
    """
    Validate OHLC price relationships and store
    every invalid row.
    """

    invalid_mask = (
        (df["high"] < df["low"]) |
        (df["open"] > df["high"]) |
        (df["open"] < df["low"]) |
        (df["close"] > df["high"]) |
        (df["close"] < df["low"])
    )

    invalid_rows = df[invalid_mask]

    result.invalid_ohlc_rows = len(invalid_rows)

    if len(invalid_rows) == 0:
        return

    if len(invalid_rows) <= 5:
        result.severity = "WARNING"
    else:
        result.severity = "FAIL"

    result.status = result.severity

    result.errors.append(
        f"{len(invalid_rows)} invalid OHLC rows"
    )

    for index, row in invalid_rows.iterrows():

        issues = []

        if row["high"] < row["low"]:
            issues.append("High < Low")

        if row["open"] > row["high"]:
            issues.append("Open > High")

        if row["open"] < row["low"]:
            issues.append("Open < Low")

        if row["close"] > row["high"]:
            issues.append("Close > High")

        if row["close"] < row["low"]:
            issues.append("Close < Low")

        result.invalid_rows.append({

            "row": index + 2,
            "date": row["date"],
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "issues": ", ".join(issues)

        })


def validate_negative_prices(df, result: ValidationResult):
    """
    Prices should never be negative.
    """

    invalid = df[
        (df["open"] < 0) |
        (df["high"] < 0) |
        (df["low"] < 0) |
        (df["close"] < 0)
    ]

    if len(invalid) > 0:
        result.status = "FAIL"
        result.errors.append(
            f"{len(invalid)} negative price rows"
        )


def validate_zero_prices(df, result: ValidationResult):
    """
    OHLC prices should never be zero.
    """

    invalid = df[
        (df["open"] == 0) |
        (df["high"] == 0) |
        (df["low"] == 0) |
        (df["close"] == 0)
    ]

    if len(invalid) > 0:
        result.status = "FAIL"
        result.errors.append(
            f"{len(invalid)} zero price rows"
        )