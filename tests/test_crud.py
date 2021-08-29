import datetime as dt

from databases import Database
from freezegun import freeze_time
import pendulum
from ward import fixture, test

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


async def _preadd_users(db: Database) -> list[int]:
    sql = """insert into
            user_ (name_)
        values
            (:name);
        """
    await db.execute_many(
        sql,
        values=[{"name": "testName1"}, {"name": "testName2"}, {"name": "testName3"}],
    )
    user_ids = await db.fetch_all("select id from user_")
    assert len(user_ids) > 0
    as_int = [user["id"] for user in user_ids]
    assert all(isinstance(user_id, int) for user_id in as_int)
    return as_int


async def _preadd_treks(db: Database, user_ids: list[int]) -> int:
    user_ids = await _preadd_users(db)
    trek_record = await crud.queries.add_trek(db, origin="testOrigin")
    trek_id = trek_record["id"]
    leg_record = await crud.queries.add_leg(
        db,
        trek_id=trek_id,
        destination="testDestination",
        added_at=pendulum.datetime(2015, 2, 5, 12, 30, 5),
    )
    leg_id = leg_record["id"]
    await crud.queries.start_leg(db, id=leg_id)

    waypoints = example_waypoints(trek_id, leg_id)
    await crud.queries.add_waypoints(db, waypoints)

    other_trek_record = await crud.queries.add_trek(db, origin="testOrigin2")
    other_trek_id = other_trek_record["id"]
    await crud.queries.add_leg(
        db,
        trek_id=other_trek_id,
        destination="testDestination2",
        added_at=pendulum.datetime(2015, 2, 6, 12, 30, 5),
    )

    users_in = [{"trek_id": trek_id, "user_id": user_id} for user_id in user_ids[0:2]]
    await crud.queries.add_trek_users(db, users_in)
    return trek_id


@test("test_add ")
async def test_add(db=connect_db, _=freeze):
    user_ids = await _preadd_users(db)
    response = await client.post(
        "/trek/",
        json={
            "origin": "testOrigin",
            "users": user_ids[0:2],
        },
    )
    assert response.json() == {"trek_id": 1}
    assert response.status_code == 200
    res = await all_rows_in_table(db, "trek")
    exp = [
        {
            "id": 1,
            "origin": "testOrigin",
        }
    ]
    assert res == exp

    res = await all_rows_in_table(db, "trek_user")
    exp = [{"trek_id": 1, "user_id": 1}, {"trek_id": 1, "user_id": 2}]
    assert res == exp


@test("test_add_leg")
async def test_add_leg(db=connect_db, _=freeze):
    user_ids = await _preadd_users(db)
    trek_id = await _preadd_treks(db, user_ids)
    response = await client.post(
        f"/trek/{trek_id}",
        json={
            "destination": "legDestination",
            "waypoints": [
                [10.681114, 59.352889, 18.35],
                [10.681664, 59.353243, 18.31],
            ],
        },
    )
    res = await all_rows_in_table(db, "leg")
    exp = {
        "destination": "legDestination",
        "id": 3,
        "is_ongoing": False,
        "added_at": dt.datetime.fromtimestamp(
            pendulum.now().timestamp(), pendulum.tz.UTC
        ),
        "trek_id": 1,
    }

    assert res[-1] == exp

    assert response.status_code == 200
    res2 = await all_rows_in_table(db, "waypoint")
    exp2 = [
        {
            "id": 5,
            "distance": 0.0,
            "elevation": 18.35,
            "lat": 10.681114,
            "leg_id": 3,
            "trek_id": 1,
            "lon": 59.352889,
        },
        {
            "id": 6,
            "distance": 72.1182134756534,
            "elevation": 18.31,
            "lat": 10.681664,
            "leg_id": 3,
            "trek_id": 1,
            "lon": 59.353243,
        },
    ]
    assert res2[-2:] == exp2


@test("test_get")
async def test_get(db=connect_db):
    user_ids = await _preadd_users(db)
    trek_id = await _preadd_treks(db, user_ids)

    response = await client.get(f"/trek/{trek_id}")
    res = response.json()
    exp = {
        "id": 1,
        "origin": "testOrigin",
        "users": [1, 2],
        "leg_id": 1,
        "leg_destination": "testDestination",
        "leg_added_at": "2015-02-05T12:30:05+00:00",
    }
    assert res == exp
    assert response.status_code == 200


@test("test_delete")
async def test_delete(db=connect_db):
    user_ids = await _preadd_users(db)
    trek_id = await _preadd_treks(db, user_ids)
    response = await client.delete(f"/trek/{trek_id}")
    assert response.status_code == 200
    res = await all_rows_in_table(db, "leg")
    assert res == [
        {
            "added_at": dt.datetime(2015, 2, 6, 12, 30, 5, tzinfo=dt.timezone.utc),
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
    exp = [{"id": 2, "origin": "testOrigin2"}]
    assert res == exp
