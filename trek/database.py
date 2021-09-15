from __future__ import annotations

import json
import logging

import aiosql
from contextlib2 import asynccontextmanager
from databases import Database
import migra
from sqlbag import S

from trek import config

log = logging.getLogger(__name__)


database_pool = Database(config.db_uri)


async def register_json_conversion(conn):
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


def split_query(query: str) -> list[str]:
    queries = query.strip().split(";")
    queries = [query.strip() for query in queries if query != ""]
    return queries


def get_db() -> Database:
    return database_pool


class DatabasesAdapter:
    is_aio_driver = True

    def process_sql(self, query_name, _op_type, sql):
        return sql

    async def select(self, conn, query_name, sql, parameters: dict, record_class=None):
        if not parameters:
            parameters = {}
        records = await conn.fetch_all(query=sql, values=parameters)
        return [record._row for record in records] if records is not None else None

    async def select_one(
        self, conn, query_name, sql, parameters: dict, record_class=None
    ):
        record = await conn.fetch_one(query=sql, values=parameters)
        return record._row if record is not None else None

    async def select_value(self, conn, query_name, sql, parameters: dict):
        record = await conn.fetch_val(query=sql, values=parameters)
        return record

    @asynccontextmanager
    async def select_cursor(self, conn, query_name, sql, parameters):
        raise NotImplementedError
        # async with MaybeAcquire(conn) as connection:
        #     stmt = await connection.prepare(sql)
        #     async with connection.transaction():
        #         yield stmt.cursor(*parameters)

    async def insert_returning(self, conn, query_name, sql, parameters: dict):
        # https://github.com/MagicStack/asyncpg/issues/47
        record = await conn.fetch_one(query=sql, values=parameters)
        return record._row if record is not None else None

    async def insert_update_delete(self, conn, query_name, sql, parameters: dict):
        for query in split_query(sql):
            await conn.execute(query=query, values=parameters)

    async def insert_update_delete_many(
        self, conn, query_name, sql, parameters: list[dict]
    ):
        for query in split_query(sql):
            await conn.execute_many(query=query, values=parameters)

    @staticmethod
    async def execute_script(conn, sql):
        for query in split_query(sql):
            await conn.execute(query)


async def setup_schema_db(db_url: str):
    schema_database = Database(db_url)
    await schema_database.connect()
    for path in ["user", "crud", "trackers"]:
        queries = aiosql.from_path(f"sql/{path}.sql", DatabasesAdapter)
        await queries.create_schema(schema_database)
    await schema_database.disconnect()


def diff_databases(db_uri: str, schema_db_uri: str):
    with S(db_uri) as current, S(schema_db_uri) as schema:
        migrations = migra.Migration(current, schema)
    return migrations


async def migrate() -> None:
    schema_db_uri = config.schema_db_uri
    db_uri = config.db_uri
    await database_pool.connect()
    queries = aiosql.from_path("sql/migrations.sql", DatabasesAdapter)
    await queries.migrations(database_pool)

    await database_pool.execute(f"drop database if exists {config.schema_db_name}")
    await database_pool.execute(f"create database {config.schema_db_name}")
    await setup_schema_db(schema_db_uri)

    previous_level = logging.root.manager.disable  # type: ignore
    logging.disable(logging.CRITICAL)
    diffs = diff_databases(db_uri, schema_db_uri)
    diffs.set_safety(False)
    diffs.add_all_changes()
    logging.disable(previous_level)
    if diffs.statements:
        print("diffs:")
        print(diffs.sql)
    else:
        print("Migrations up to date")
    # await database_pool.execute(f"drop database if exists {config.schema_db_name}")
