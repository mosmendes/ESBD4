
import os
from sqlalchemy import create_engine, text
from tenacity import retry, stop_after_attempt, wait_fixed

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/testdb")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

@retry(stop=stop_after_attempt(10), wait=wait_fixed(2))
def write_to_db(key: str, value: str, version: int):
    with engine.begin() as conn:
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
