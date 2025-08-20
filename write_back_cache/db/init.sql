
CREATE TABLE IF NOT EXISTS cache_data (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    version BIGINT NOT NULL
);
