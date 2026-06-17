import os
import re
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

def load_env_db_urls():
    """Manually parse .env file to get DATABASE_SYNC_URL."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        print("Error: .env file not found in backend directory.", file=sys.stderr)
        sys.exit(1)

    sync_url = None
    with open(env_path, "r") as f:
        for line in f:
            if line.strip().startswith("DATABASE_SYNC_URL="):
                sync_url = line.split("=", 1)[1].strip()
                break

    if not sync_url:
        # Fallback default
        sync_url = "postgresql://postgres:admin123@localhost:5432/bgv_db"
    
    return sync_url

def create_database():
    sync_url = load_env_db_urls()

    # We need to extract the base URL connecting to the default 'postgres' database
    # Example URL: postgresql://postgres:admin123@localhost:5432/bgv_db
    # We want to replace '/bgv_db' with '/postgres'
    match = re.search(r"^(postgresql(?:\+psycopg2)?://[^/]+)/([^?]+)", sync_url)
    if not match:
        print(f"Error: Could not parse database URL: {sync_url}", file=sys.stderr)
        sys.exit(1)

    base_url = match.group(1)
    target_db = match.group(2)
    default_db_url = f"{base_url}/postgres"

    print(f"Connecting to default PostgreSQL database to check/create '{target_db}'...")
    
    # Create engine connecting to the default 'postgres' database
    # AUTOCOMMIT is required because CREATE DATABASE cannot be executed inside a transaction block
    engine = create_engine(default_db_url, isolation_level="AUTOCOMMIT")

    try:
        with engine.connect() as conn:
            # Check if database already exists
            result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{target_db}'"))
            exists = result.scalar() is not None

            if not exists:
                print(f"Database '{target_db}' does not exist. Creating...")
                conn.execute(text(f"CREATE DATABASE {target_db}"))
                print(f"Database '{target_db}' created successfully!")
            else:
                print(f"Database '{target_db}' already exists.")
    except Exception as e:
        print(f"Error connecting to or creating database: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    create_database()
