import datetime as dt

from asyncpg import Connection
import pendulum
from ward import test

from tests.conftest import all_rows_in_table, connect_db
from trek import crud
from trek.progress.progress_utils import queries


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


async def _preadd_treks(db: Connection, user_ids: list[int]) -> tuple[int, int]:
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
    return trek_id, leg_id


@test("treks_to_update_1_days_since_last_20h")
async def test_treks_to_update_1_days_since_last_20h(db=connect_db):
    user_ids = await _preadd_users(db)
    trek_id, leg_id = await _preadd_treks(db, user_ids)
    await queries.add_location(
        db,
        trek_id=trek_id,
        leg_id=leg_id,
        visited_at=pendulum.date(2015, 2, 7),
        address="my_address",
    )
    now = dt.datetime(2015, 2, 9, 20, 0, 0)
    res = await queries.treks_to_update(db, now=now)
    assert len(res) == 1
    exp = {
        "trek_id": 1,
        "leg_id": 1,
        "most_recent_location_date": pendulum.date(2015, 2, 7),
        "execute_yesterdays_progress": True,
    }
    assert dict(res[0]) == exp


@test("treks_to_update_1_days_since_last_10h")
async def test_treks_to_update_1_days_since_last_10h(db=connect_db):
    user_ids = await _preadd_users(db)
    trek_id, leg_id = await _preadd_treks(db, user_ids)
    await queries.add_location(
        db,
        trek_id=trek_id,
        leg_id=leg_id,
        visited_at=pendulum.date(2015, 2, 7),
        address="my_address",
    )
    now = dt.datetime(2015, 2, 9, 10, 0, 0)
    res = await queries.treks_to_update(db, now=now)
    assert res == []


@test("treks_to_update_0_days_since_last_20h")
async def test_treks_to_update_0_days_since_last_20h(db=connect_db):
    user_ids = await _preadd_users(db)
    trek_id, leg_id = await _preadd_treks(db, user_ids)
    await queries.add_location(
        db,
        trek_id=trek_id,
        leg_id=leg_id,
        visited_at=pendulum.date(2015, 2, 8),
        address="my_address",
    )
    now = dt.datetime(2015, 2, 9, 20, 0, 0)
    res = await queries.treks_to_update(db, now=now)
    assert res == []


@test("treks_to_update_2_days_since_last_10h")
async def test_treks_to_update_2_days_since_last_10h(db=connect_db):
    user_ids = await _preadd_users(db)
    trek_id, leg_id = await _preadd_treks(db, user_ids)
    await queries.add_location(
        db,
        trek_id=trek_id,
        leg_id=leg_id,
        visited_at=pendulum.date(2015, 2, 6),
        address="my_address",
    )
    now = dt.datetime(2015, 2, 9, 10, 0, 0)
    res = await queries.treks_to_update(db, now=now)
    assert len(res) == 1
    exp = {
        "trek_id": 1,
        "leg_id": 1,
        "most_recent_location_date": pendulum.date(2015, 2, 6),
        "execute_yesterdays_progress": False,
    }
    assert dict(res[0]) == exp
