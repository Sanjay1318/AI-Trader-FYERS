import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load .env file
load_dotenv()

# Get credentials from .env
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'ai-trader-2026')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'trading')

# Build connection string
connection_string = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

print(f"🔌 Connecting to: {DB_HOST}:{DB_PORT}/{DB_NAME}")

# Test connection
engine = create_engine(connection_string)
with engine.connect() as conn:
    result = conn.execute(text("SELECT version()"))
    print("✅ Database Connected Successfully!")
    print(result.fetchone()[0])