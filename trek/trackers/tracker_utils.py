import aiosql

queries = aiosql.from_path("sql/trackers.sql", driver_adapter="asyncpg")
