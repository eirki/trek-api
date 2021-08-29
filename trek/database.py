from __future__ import annotations

from contextlib2 import asynccontextmanager
from databases import Database

from trek import env

database = Database(env.db_uri)
# TODO replace Database with raw asyncpg
# TODO handle migration with migra


def split_query(query: str) -> list[str]:
    queries = query.strip().split(";")
    queries = [query.strip() for query in queries if query != ""]
    return queries


def get_db() -> Database:
    return database


class DatabasesAdapter:
    is_aio_driver = True

    def process_sql(self, query_name, _op_type, sql):
        return sql

    async def select(self, conn, query_name, sql, parameters, record_class=None):
        if not parameters:
            parameters = {}
        records = await conn.fetch_all(query=sql, values=parameters)
        return [record._row for record in records] if records is not None else None

    async def select_one(self, conn, query_name, sql, parameters, record_class=None):
        record = await conn.fetch_one(query=sql, values=parameters)
        return record._row if record is not None else None

    async def select_value(self, conn, query_name, sql, parameters):
        record = await conn.fetch_val(query=sql, values=parameters)
        return record._row if record is not None else None

    @asynccontextmanager
    async def select_cursor(self, conn, query_name, sql, parameters):
        raise NotImplementedError
        # async with MaybeAcquire(conn) as connection:
        #     stmt = await connection.prepare(sql)
        #     async with connection.transaction():
        #         yield stmt.cursor(*parameters)

    async def insert_returning(self, conn, query_name, sql, parameters):
        # https://github.com/MagicStack/asyncpg/issues/47
        record = await conn.fetch_one(query=sql, values=parameters)
        return record._row if record is not None else None

    async def insert_update_delete(self, conn, query_name, sql, parameters):
        for query in split_query(sql):
            await conn.execute(query=query, values=parameters)

    async def insert_update_delete_many(self, conn, query_name, sql, parameters):
        for query in split_query(sql):
            await conn.execute_many(query=query, values=parameters)

    @staticmethod
    async def execute_script(conn, sql):
        for query in split_query(sql):
            await conn.execute(query)
