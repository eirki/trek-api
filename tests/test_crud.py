import datetime as dt

from asyncpg import Connection
from asyncpg.exceptions import UniqueViolationError
from freezegun import freeze_time
import pendulum
from psycopg.rows import dict_row
from ward import fixture, raises, test

from tests import conftest
from tests.conftest import all_rows_in_table, client, connect_db
from trek import crud


@fixture
def freeze():
    with freeze_time("2012-01-14"):
        yield


def example_waypoints(trek_id: int, leg_id: int) -> list[dict]:
    return [
        {
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": 10.671114,
            "lon": 59.332889,
            "elevation": 18.35,
            "distance": 0.0,
        },
        {
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": 10.671664,
            "lon": 59.333243,
            "elevation": 18.31,
            "distance": 72.11886064837488,
        },
        {
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": 10.671857,
            "lon": 59.333329,
            "elevation": 18.32,
            "distance": 95.44853837588332,
        },
        {
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": 10.672099,
            "lon": 59.333292,
            "elevation": 17.51,
            "distance": 122.52108499023316,
        },
    ]


async def _preadd_users(db: Connection) -> list[int]:
    sql = """insert into
            user_ (is_admin)
        values
            (:is_admin);
        """
    await db.execute_many(sql, values=[{"is_admin": False}] * 3)
    user_ids = await db.fetch_all("select id from user_")
    assert len(user_ids) > 0
    as_int = [user["id"] for user in user_ids]
    assert all(isinstance(user_id, int) for user_id in as_int)
    return as_int


async def _preadd_treks(db: Connection, user_ids: list[int]) -> int:
    trek_record = await crud.queries.add_trek(
        db, origin="testOrigin", owner_id=user_ids[0]
    )
    trek_id = trek_record["id"]
    leg_record = await crud.queries.add_leg(
        db,
        trek_id=trek_id,
        destination="testDestination",
        added_at=pendulum.datetime(2015, 2, 5, 12, 30, 5),
        added_by=user_ids[0],
    )
    leg_id = leg_record["id"]
    await crud.queries.start_leg(db, id=leg_id)

    waypoints = example_waypoints(trek_id, leg_id)
    await crud.queries.add_waypoints(db, waypoints)

    other_trek_record = await crud.queries.add_trek(
        db, origin="testOrigin2", owner_id=user_ids[1]
    )
    other_trek_id = other_trek_record["id"]
    await crud.queries.add_leg(
        db,
        trek_id=other_trek_id,
        destination="testDestination2",
        added_at=pendulum.datetime(2015, 2, 6, 12, 30, 5),
        added_by=user_ids[1],
    )

    for user_id in user_ids[0:2]:
        now = dt.datetime.fromtimestamp(pendulum.now().timestamp(), pendulum.tz.UTC)
        await crud.queries.add_trek_user(
            db, trek_id=trek_id, user_id=user_id, added_at=now
        )
    return trek_id


if True:
    import asyncio

    import asyncpg
    import psycopg
    from testcontainers.postgres import PostgresContainer
    from ward import fixture

    from trek import crud, main, user, utils


@fixture(scope="global")
async def fix():
    with PostgresContainer(image="postgres:13.3") as postgres:
        db_uri = postgres.get_connection_url().replace("+psycopg2", "")
        # yield db_test_uri
        async with await psycopg.AsyncConnection.connect(
            db_uri, row_factory=dict_row
        ) as db:
            async with db.transaction(force_rollback=True):
                yield db


@fixture
async def fax(db_url=fix):
    async with await psycopg.AsyncConnection.connect(db_url) as db:
        async with db.transaction(force_rollback=True):
            await crud.queries.create_schema(db)
            yield db
    # await test_database.close()


@test("blarg")
async def blarg(test_database=fax):
    # loop = asyncio.get_event_loop()
    res = await test_database.execute("SELECT 1")
    res = await res.fetchone()
    # yield test_database

    assert res is None


@test("blorg")
async def blorg(db=fix):
    # with PostgresContainer(image="postgres:13.3") as postgres:
    # db_uri = postgres.get_connection_url().replace("+psycopg2", "")
    # test_database = await asyncpg.connect(dsn=db_uri)
    await user.queries.create_schema(db)
    await crud.queries.add_trek(db)
    async with db.cursor() as acur:
        await acur.execute("SELECT * from user_")
        res = await acur.fetchone()
        # will return (1, 100, "abc'def")
        async for record in acur:
            print(record)
            # async with test_database.transaction(force_rollback=True):
            #     # yield test_database
            #     # res = await test_database.fetchone("SELECT 1")
            #     await test_database.execute("SELECT 1")
            #     await acur.execute("SELECT * FROM test")
            #     await acur.fetchone()
            #     # will return (1, 100, "abc'def")
            #     async for record in acur:
            #         print(record)
            #     res = await test_database.fetchone()
    assert res is None


@test("test_add_trek")
async def test_add_trek(
    db=connect_db,
    _a=freeze,
    _b=conftest.overide(conftest.auth_overrides()),
):
    await _preadd_users(db)
    response = await client.post(
        "/trek/",
        json={
            "origin": "testOrigin",
            "waypoints": [
                [10.681114, 59.352889, 18.35],
                [10.681664, 59.353243, 18.31],
            ],
            "destination": "testDestination",
        },
    )
    assert response.json() == {"trek_id": 1, "leg_id": 1}
    assert response.status_code == 200, response.text
    res = await all_rows_in_table(db, "trek")
    exp = [
        {
            "id": 1,
            "origin": "testOrigin",
            "owner_id": 1,
            "progress_at": "12:00:00 CET",
        }
    ]
    assert res == exp

    res = await all_rows_in_table(db, "trek_user")

    exp = [
        {
            "added_at": dt.datetime(2012, 1, 14, 0, 0, tzinfo=dt.timezone.utc),
            "trek_id": 1,
            "user_id": 1,
        }
    ]
    assert res == exp


@test("test_add_leg")
async def test_add_leg(
    db=connect_db,
    _a=freeze,
    _b=conftest.overide(conftest.auth_overrides(user_id=2)),
):
    user_ids = await _preadd_users(db)
    trek_id = await _preadd_treks(db, user_ids)
    legs = await crud.queries.get_legs_for_trek(db, trek_id=trek_id)
    prev_lev = legs[-1]
    await db.execute(
        "update leg set is_ongoing = false where leg.id = :id",
        values={"id": prev_lev["id"]},
    )

    response = await client.post(
        f"/trek/{trek_id}",
        json={
            "destination": "legDestination",
            "waypoints": [
                [10.672099, 59.333292, 17.51],
                [10.681114, 59.352889, 18.35],
                [10.681664, 59.353243, 18.31],
            ],
        },
    )
    assert response.status_code == 200, response.text

    res = await all_rows_in_table(db, "leg")
    exp = {
        "destination": "legDestination",
        "id": 3,
        "is_ongoing": True,
        "added_at": dt.datetime.fromtimestamp(
            pendulum.now().timestamp(), pendulum.tz.UTC
        ),
        "added_by": 2,
        "trek_id": 1,
    }

    assert res[-1] == exp

    res2 = await all_rows_in_table(db, "waypoint")
    exp2 = [
        {
            "id": 6,
            "distance": 2364.5557187057007,
            "elevation": 18.35,
            "lat": 10.681114,
            "leg_id": 3,
            "trek_id": 1,
            "lon": 59.352889,
        },
        {
            "id": 7,
            "distance": 2436.673932181354,
            "elevation": 18.31,
            "lat": 10.681664,
            "leg_id": 3,
            "trek_id": 1,
            "lon": 59.353243,
        },
    ]
    assert res2[-2:] == exp2


@test("test_get")
async def test_get(
    db=connect_db,
    _=conftest.overide(conftest.auth_overrides()),
):
    user_ids = await _preadd_users(db)
    trek_id = await _preadd_treks(db, user_ids)

    response = await client.get(f"/trek/{trek_id}")
    res = response.json()
    exp = {
        "is_owner": True,
        "origin": "testOrigin",
        "users": [1, 2],
        "legs": [
            {
                "added_at": "2015-02-05T12:30:05+00:00",
                "destination": "testDestination",
                "id": 1,
            }
        ],
    }
    assert res == exp
    assert response.status_code == 200, response.text


@test("test_delete")
async def test_delete(
    db=connect_db,
    _=conftest.overide(conftest.auth_overrides()),
):
    user_ids = await _preadd_users(db)
    trek_id = await _preadd_treks(db, user_ids)
    response = await client.delete(f"/trek/{trek_id}")
    assert response.status_code == 200, response.text
    res = await all_rows_in_table(db, "leg")
    assert res == [
        {
            "added_at": dt.datetime(2015, 2, 6, 12, 30, 5, tzinfo=dt.timezone.utc),
            "added_by": 2,
            "destination": "testDestination2",
            "id": 2,
            "is_ongoing": False,
            "trek_id": 2,
        }
    ]
    res = await all_rows_in_table(db, "waypoint")
    assert res == []
    res = await all_rows_in_table(db, "trek_user")
    assert res == []
    res = await all_rows_in_table(db, "trek")
    exp = [
        {
            "id": 2,
            "origin": "testOrigin2",
            "owner_id": 2,
            "progress_at": "12:00:00 CET",
        }
    ]
    assert res == exp


@test("test_two_ongoing_legs_fail")
async def test_two_ongoing_legs_fail(db=connect_db):
    user_ids = await _preadd_users(db)
    trek_record = await crud.queries.add_trek(
        db, origin="testOrigin", owner_id=user_ids[0]
    )
    trek_id = trek_record["id"]
    leg_record = await crud.queries.add_leg(
        db,
        trek_id=trek_id,
        destination="testDestination",
        added_at=pendulum.datetime(2015, 2, 5, 12, 30, 5),
        added_by=user_ids[0],
    )
    leg_id = leg_record["id"]
    await crud.queries.start_leg(db, id=leg_id)

    leg_record = await crud.queries.add_leg(
        db,
        trek_id=trek_id,
        destination="testDestination2",
        added_at=pendulum.datetime(2015, 2, 5, 12, 30, 5),
        added_by=user_ids[1],
    )
    leg_id = leg_record["id"]
    with raises(UniqueViolationError):
        await crud.queries.start_leg(db, id=leg_id)


@test("test_generate_invite")
async def test_generate_invite(
    db=connect_db,
    _=conftest.overide(conftest.auth_overrides()),
):
    user_ids = await _preadd_users(db)
    trek_id = await _preadd_treks(db, user_ids)
    response = await client.get(f"/trek/invite/{trek_id}/")
    res = response.json()
    assert "invite_id" in res
    decrypted_trek_id = crud.decrypt_id(res["invite_id"])
    assert trek_id == decrypted_trek_id


@test("test_add_user_to_trek")
async def test_add_user_to_trek(
    db=connect_db,
    _=conftest.overide(conftest.auth_overrides(user_id=4)),
):
    user_ids = await _preadd_users(db)
    trek_id = await _preadd_treks(db, user_ids)
    encrypted_trek_id = crud.encrypt_id(trek_id)
    sql = """insert into
            user_ (is_admin)
        values
            (:is_admin)
        returning
            id;
        """
    user_id = await db.fetch_val(sql, values={"is_admin": False})
    assert user_id == 4  # ugly
    response = await client.get(f"/trek/join/{encrypted_trek_id}/")
    assert response.status_code == 201
    records = await db.fetch_all(
        "select user_id from trek_user where trek_id = :trek_id",
        values={"trek_id": trek_id},
    )
    trek_user_ids = [record["user_id"] for record in records]
    assert 4 in trek_user_ids
    response = await client.get(f"/trek/join/{encrypted_trek_id}/")
    assert response.status_code == 200, response.text


@test("next_leg_adder")
async def test_next_leg_adder(
    db=connect_db,
    _=conftest.overide(conftest.auth_overrides(user_id=4)),
):
    user_ids = await _preadd_users(db)
    trek_record = await crud.queries.add_trek(
        db, origin="testOrigin", owner_id=user_ids[0]
    )
    trek_id = trek_record["id"]
    for user_id in user_ids[0:2]:
        now = dt.datetime.fromtimestamp(pendulum.now().timestamp(), pendulum.tz.UTC)
        await crud.queries.add_trek_user(
            db, trek_id=trek_id, user_id=user_id, added_at=now
        )

    leg_record = await crud.queries.add_leg(
        db,
        trek_id=trek_id,
        destination="testDestination",
        added_at=pendulum.datetime(2015, 2, 5, 12, 30, 5),
        added_by=user_ids[0],
    )
    leg_id = leg_record["id"]
    prev_adder_id = await crud.queries.prev_adder_id(db, leg_id=leg_id)
    next_adder_id = await crud.queries.next_adder_id(
        db, prev_adder_id=prev_adder_id, trek_id=trek_id
    )
    assert next_adder_id == user_ids[1]


@test("next_leg_adder_first")
async def test_next_leg_adder_first(
    db=connect_db,
    _=conftest.overide(conftest.auth_overrides(user_id=4)),
):
    user_ids = await _preadd_users(db)
    trek_record = await crud.queries.add_trek(
        db, origin="testOrigin", owner_id=user_ids[0]
    )
    trek_id = trek_record["id"]
    for user_id in user_ids[0:2]:
        now = dt.datetime.fromtimestamp(pendulum.now().timestamp(), pendulum.tz.UTC)
        await crud.queries.add_trek_user(
            db, trek_id=trek_id, user_id=user_id, added_at=now
        )

    leg_record = await crud.queries.add_leg(
        db,
        trek_id=trek_id,
        destination="testDestination",
        added_at=pendulum.datetime(2015, 2, 5, 12, 30, 5),
        added_by=user_ids[1],
    )
    leg_id = leg_record["id"]
    prev_adder_id = await crud.queries.prev_adder_id(db, leg_id=leg_id)
    next_adder_id = await crud.queries.next_adder_id(
        db, prev_adder_id=prev_adder_id, trek_id=trek_id
    )
    assert next_adder_id == user_ids[0]
