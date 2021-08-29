import typing as t

from async_asgi_testclient import TestClient
from databases import Database
from testcontainers.postgres import PostgresContainer
from ward import fixture

from trek import crud, main, user
from trek.database import get_db

client = TestClient(main.app)


@fixture(scope="global")
async def setup_db():
    with PostgresContainer(image="postgres:13.3") as postgres:
        db_test_uri = postgres.get_connection_url().replace("+psycopg2", "")
        test_database = Database(db_test_uri, force_rollback=True)

        await test_database.connect()
        async with test_database.transaction(force_rollback=True):
            await user.queries.create_schema(test_database)
            await crud.queries.create_schema(test_database)
            yield test_database

        await test_database.disconnect()


@fixture
async def connect_db(db=setup_db):
    async with db.transaction(force_rollback=True):

        async def get_test_db() -> t.AsyncIterator[Database]:
            yield db  # yield to endpoint

        main.app.dependency_overrides[get_db] = get_test_db
        yield db  # yield to test

    await reset_sequences(db)


async def reset_sequences(db):
    async with db.transaction():
        sequences = await db.fetch_all(
            query="SELECT * FROM information_schema.sequences"
        )
        for seq in sequences:
            await db.execute(
                query=f"ALTER SEQUENCE {seq['sequence_name']} RESTART WITH 1"
            )


async def all_rows_in_table(db, table: str):
    records = await db.fetch_all(f"select * from {table}")
    as_dict = [dict(record) for record in records]
    return as_dict
