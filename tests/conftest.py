import typing as t

from async_asgi_testclient import TestClient
from databases import Database
from testcontainers.postgres import PostgresContainer
from ward import fixture

from trek import main, trek, user
from trek.database import get_db

client = TestClient(main.app)


@fixture
async def connect_db():
    with PostgresContainer(image="postgres:13.3") as postgres:
        db_test_uri = postgres.get_connection_url().replace("+psycopg2", "")
        test_database = Database(db_test_uri, force_rollback=True)

        await test_database.connect()
        async with test_database.transaction():
            await user.queries.create_schema(test_database)
            await trek.queries.create_schema(test_database)

            async def get_test_db() -> t.AsyncIterator[Database]:
                async with test_database.transaction():
                    yield test_database

            main.app.dependency_overrides[get_db] = get_test_db

            yield test_database
            await test_database.disconnect()
