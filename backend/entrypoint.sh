#!/bin/sh

set -e

echo "======================================"
echo "BGV Backend Starting..."
echo "Running database migrations..."
echo "======================================"

# Ensure the database exists before migrations run
python -c "
import os, urllib.parse, psycopg2, time
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
url_str = os.environ.get('DATABASE_SYNC_URL', '')
if url_str.startswith('postgresql'):
    u = urllib.parse.urlparse(url_str)
    for i in range(10):
        try:
            c = psycopg2.connect(dbname='postgres', user=u.username, password=u.password, host=u.hostname, port=u.port or 5432)
            c.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cur = c.cursor()
            cur.execute('SELECT 1 FROM pg_database WHERE datname=%s', (u.path.lstrip('/'),))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE \"{u.path.lstrip(\"/\")}\"')
            cur.close()
            c.close()
            break
        except Exception as e:
            print(f'DB connection attempt {i+1} failed:', e)
            time.sleep(2)
"

# Run Alembic migrations
alembic upgrade head

echo "======================================"
echo "Migrations completed successfully"
echo "Starting FastAPI application..."
echo "======================================"

# Start backend
uvicorn app.main:app --host 0.0.0.0 --port 8000