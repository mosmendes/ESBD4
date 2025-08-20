
import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from tenacity import retry, stop_after_attempt, wait_fixed

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/testdb")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

@retry(stop=stop_after_attempt(10), wait=wait_fixed(2))
def write_to_db(key: str, value: str, version: int):
    with engine.begin() as conn:
        # Only update if incoming version is newer or equal (last-write-wins)
        conn.execute(
            text("""
                INSERT INTO cache_data (key, value, version)
                VALUES (:key, :value, :version)
                ON CONFLICT (key)
                DO UPDATE SET value = EXCLUDED.value, version = EXCLUDED.version
                WHERE EXCLUDED.version >= cache_data.version
            """),
            {"key": key, "value": value, "version": version}
        )

@retry(stop=stop_after_attempt(10), wait=wait_fixed(2))
def read_from_db(key: str):
    with engine.begin() as conn:
        res = conn.execute(text("SELECT value, version FROM cache_data WHERE key=:key"), {"key": key}).first()
        return res if res else None
