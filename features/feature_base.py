"""
Feature Module Base Class
──────────────────────────
Defines the common interface that all feature modules must implement.

Each module takes a DataFrame, computes its indicators, and returns
the augmented DataFrame with new columns added. Modules are composable
and independent — they never call each other.
"""

from abc import ABC, abstractmethod
from typing import List

import pandas as pd

from utils.logger import get_logger

logger = get_logger("feature_base")


class BaseFeatureModule(ABC):
    """Abstract base class for all feature computation modules."""

    @abstractmethod
    def required_columns(self) -> List[str]:
        """
        Return the list of column names the module needs in the input DataFrame.
        Used for early validation before compute() is called.
        """
        ...

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute features on the input DataFrame.
        Must return a DataFrame with the same index and all original columns
        plus any new feature columns added.

        Args:
            df: Input DataFrame with at least the columns from required_columns().

        Returns:
            DataFrame with original columns + new feature columns.
        """
        ...

    def validate_input(self, df: pd.DataFrame) -> None:
        """Validate that all required columns exist in the input DataFrame."""
        missing = [c for c in self.required_columns() if c not in df.columns]
        if missing:
            raise ValueError(
                f"{self.__class__.__name__}: missing required columns: {missing}"
            )

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convenience method so modules can be called directly:
            result = TechnicalFeatures()(df)
        """
        return self.compute(df)

