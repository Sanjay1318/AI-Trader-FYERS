#!/usr/bin/env python3
"""Standalone database initialization script."""
import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))

print("[*] Initializing database schema...")

try:
    from database.db import init_db
    print("[*] Testing database connection...")
    init_db()
    print("[✓] Database schema initialized successfully!")
    sys.exit(0)
except ConnectionRefusedError as e:
    print(f"[!] Connection refused: {e}")
    print("[!] PostgreSQL is not running. Please start PostgreSQL and try again.")
    sys.exit(1)
except Exception as e:
    print(f"[!] Error during initialization: {type(e).__name__}")
    print(f"[!] Details: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
