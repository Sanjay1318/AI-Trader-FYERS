from pathlib import Path
import pandas as pd


class ValidationResult:

    def __init__(self):

        self.file_name = ""

        self.rows = 0
        self.columns = 0

        self.start_date = None
        self.end_date = None

        self.missing_values = 0
        self.duplicate_rows = 0
        self.duplicate_timestamps = 0

        self.status = "PASS"
        self.severity = "PASS"

        self.errors = []

        # New
        self.invalid_ohlc_rows = 0
        self.invalid_rows = []
        self.execution_time = 0
        self.quality_score = 100.0


def load_csv(file_path: Path) -> pd.DataFrame:
    """
    Load CSV into a pandas DataFrame.
    """

    return pd.read_csv(file_path)


def basic_info(df: pd.DataFrame, result: ValidationResult):

    result.rows = len(df)
    result.columns = len(df.columns)


def check_missing_values(df: pd.DataFrame, result: ValidationResult):

    result.missing_values = int(df.isnull().sum().sum())

    if result.missing_values > 0:
        result.status = "FAIL"
        result.errors.append("Missing values found")


def check_duplicate_rows(df: pd.DataFrame, result: ValidationResult):

    result.duplicate_rows = int(df.duplicated().sum())

    if result.duplicate_rows > 0:
        result.status = "FAIL"
        result.errors.append("Duplicate rows found")


def check_date_column(df: pd.DataFrame, result: ValidationResult):

    if "date" not in df.columns:
        result.status = "FAIL"
        result.errors.append("Date column missing")
        return

    df["date"] = pd.to_datetime(df["date"])

    result.start_date = df["date"].min()
    result.end_date = df["date"].max()

    result.duplicate_timestamps = int(df["date"].duplicated().sum())

    if result.duplicate_timestamps > 0:
        result.status = "FAIL"
        result.errors.append("Duplicate timestamps found")