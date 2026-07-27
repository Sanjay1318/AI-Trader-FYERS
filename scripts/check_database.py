"""
Quick database inspection script.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from database.db import read_sql


def main():
    # Check market_features table
    df = read_sql("SELECT COUNT(*) as cnt FROM market_features")
    print(f"Rows in market_features: {df.iloc[0]['cnt']}")

    # Check distinct regimes
    df2 = read_sql(
        "SELECT regime, COUNT(*) as cnt FROM market_features "
        "GROUP BY regime ORDER BY cnt DESC"
    )
    print("\nRegime distribution:")
    for _, r in df2.iterrows():
        print(f"  {r['regime']}: {r['cnt']}")

    # Check sessions
    df3 = read_sql(
        "SELECT session, COUNT(*) as cnt FROM market_features "
        "GROUP BY session ORDER BY cnt DESC"
    )
    print("\nSession distribution:")
    for _, r in df3.iterrows():
        print(f"  {r['session']}: {r['cnt']}")

    # Latest 5 rows
    df4 = read_sql(
        "SELECT timestamp, close, rsi, ema20, ema50, regime, session "
        "FROM market_features ORDER BY timestamp DESC LIMIT 5"
    )
    print("\nLatest 5 rows:")
    for _, r in df4.iterrows():
        print(f"  {r['timestamp']} | close={r['close']:.1f} | rsi={r['rsi']:.1f} | "
              f"ema20={r['ema20']:.1f} | regime={r['regime']} | session={r['session']}")

    # Date range
    df5 = read_sql(
        "SELECT MIN(timestamp::date) as first, MAX(timestamp::date) as last "
        "FROM market_features"
    )
    print(f"\nDate range: {df5.iloc[0]['first']} -> {df5.iloc[0]['last']}")

    # Columns
    df6 = read_sql(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'market_features' ORDER BY ordinal_position"
    )
    print(f"\nColumns ({len(df6)}):")
    for _, r in df6.iterrows():
        print(f"  {r['column_name']:25s} {r['data_type']}")


if __name__ == "__main__":
    main()
