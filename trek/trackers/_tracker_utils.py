import aiosql

from trek.database import DatabasesAdapter

queries = aiosql.from_path("sql/trackers.sql", driver_adapter=DatabasesAdapter)
