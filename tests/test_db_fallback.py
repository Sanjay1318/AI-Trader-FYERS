import pandas as pd

from database import db


def test_read_sql_returns_empty_dataframe_when_db_fails(monkeypatch):
    class BrokenConnection:
        def __enter__(self):
            raise RuntimeError("db unavailable")

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(db.engine, "connect", lambda: BrokenConnection())

    result = db.read_sql("SELECT 1")

    assert isinstance(result, pd.DataFrame)
    assert result.empty
