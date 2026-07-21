#!/usr/bin/env python3
"""Direct database initialization using psycopg2."""
import psycopg2
import os
from pathlib import Path

# Load .env
from dotenv import load_dotenv
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "trading")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

print(f"[*] Connecting to {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}...")

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    print("[✓] Connected successfully")
    
    # Read and execute schema
    schema_path = Path(__file__).parent / "database" / "schema.sql"
    with open(schema_path, "r") as f:
        sql = f.read()
    
    print(f"[*] Executing schema from {schema_path}...")
    
    # Execute the complete additive schema, including statements preceded by
    # comments. psycopg2 handles the multi-statement PostgreSQL script.
    cursor.execute(sql)
    count = 1
    
    conn.commit()
    print(f"[✓] Schema initialized! Executed {count} statements")
    cursor.close()
    conn.close()
    
except psycopg2.Error as e:
    print(f"[!] Database error: {e}")
    exit(1)
except Exception as e:
    print(f"[!] Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
