from __future__ import annotations

import logging
import typing as t

import aiosql
import asyncpg
from asyncpg import Connection
import migra
from sqlbag import S

from trek import config

log = logging.getLogger(__name__)

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=config.db_uri)
    return _pool


async def get_db() -> t.AsyncIterator[Connection]:
    pool = await get_pool()
    async with pool.acquire() as db:
        yield db


async def _setup_schema_db(db_url: str):
    schema_database = await asyncpg.connect(dsn=db_url)
    for path in ["user", "crud", "trackers"]:
        queries = aiosql.from_path(f"sql/{path}.sql", "psycopg")
        await queries.create_schema(schema_database)
    await schema_database.close()


def _diff_databases(db_uri: str, schema_db_uri: str):
    with S(db_uri) as current, S(schema_db_uri) as schema:
        migrations = migra.Migration(current, schema)
    return migrations


async def migrate() -> None:
    schema_db_uri = config.schema_db_uri
    db_uri = config.db_uri
    pool = await get_pool()
    db: Connection
    async with pool.acquire() as db:
        queries = aiosql.from_path("sql/migrations.sql", "psycopg")
        await queries.migrations(db)

        await db.execute(f"drop database if exists {config.schema_db_name}")
        await db.execute(f"create database {config.schema_db_name}")
        await _setup_schema_db(schema_db_uri)

        previous_level = logging.root.manager.disable  # type: ignore
        logging.disable(logging.CRITICAL)
        diffs = _diff_databases(db_uri, schema_db_uri)
        diffs.set_safety(False)
        diffs.add_all_changes()
        logging.disable(previous_level)
        if diffs.statements:
            print("diffs:")
            print(diffs.sql)
        else:
            print("Migrations up to date")
    # await db.execute(f"drop database if exists {config.schema_db_name}")
