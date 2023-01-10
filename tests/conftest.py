import typing as t

from async_asgi_testclient import TestClient
import asyncpg
from asyncpg import Connection
from fastapi_jwt_auth import AuthJWT
from testcontainers.postgres import PostgresContainer
from ward import fixture

from trek import crud, main, user, utils
from trek.database import get_db
from trek.progress import progress_utils
from trek.trackers import tracker_utils

client = TestClient(main.app)


async def _create_schema(db):
    await user.queries.create_schema(db)
    await crud.queries.create_schema(db)
    await tracker_utils.queries.create_schema(db)
    await progress_utils.queries.create_schema(db)


@fixture(scope="global")
async def setup_db():
    with PostgresContainer(image="postgres:13.3") as postgres:
        db_test_uri = postgres.get_connection_url().replace("+psycopg2", "")
        yield db_test_uri


@fixture
async def connect_db(db_uri: str = setup_db):
    db = await asyncpg.connect(dsn=db_uri)
    tr = db.transaction()
    await _create_schema(db)
    await tr.start()
    try:

        async def get_test_db() -> t.AsyncIterator[Connection]:
            yield db  # yield to endpoint

        main.app.dependency_overrides[get_db] = get_test_db
        yield db  # yield to test
        del main.app.dependency_overrides[get_db]
    finally:
        await tr.rollback()
        await db.close()
    # await reset_sequences(db)


# async def reset_sequences(db):
#     async with db.transaction():
#         sequences = await db.fetch_all(
#             query="SELECT * FROM information_schema.sequences"
#         )
#         for seq in sequences:
#             await db.execute(
#                 query=f"ALTER SEQUENCE {seq['sequence_name']} RESTART WITH 1"
#             )


async def all_rows_in_table(db, table: str):
    records = await db.fetch_all(f"select * from {table}")
    as_dict = [dict(record) for record in records]
    return as_dict


class FakeAuth:
    def __init__(self, user_id=1):
        self.user_id = user_id

    def __call__(self):
        return self

    def jwt_required(self):
        pass

    def get_jwt_subject(self):
        return self.user_id

    def create_access_token(self, subject):
        return f"access_token-{subject}"


def overide(overrides: dict, container: dict = main.app.dependency_overrides):
    @fixture
    def inner():
        old_container = container.copy()
        container.update(overrides)
        yield
        # mutably reset overrides after test
        keys = set(container)
        for key in keys:
            del container[key]
        container.update(old_container)

    return inner


def auth_overrides(user_id=1):
    return {
        AuthJWT: FakeAuth(user_id=user_id),
        utils.protect_endpoint: lambda: None,
    }
