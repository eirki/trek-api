from databases import Database
from ward import test

from tests.conftest import client, connect_db
from trek import trek


async def all_rows_in_table(db, table: str):
    records = await db.fetch_all(f"select * from {table}")
    as_dict = [dict(record) for record in records]
    return as_dict


async def add_users(db: Database) -> list[int]:
    sql = """insert into
            user_ (name)
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


async def add_treks(db: Database, user_ids: list[int]) -> int:
    user_ids = await add_users(db)
    trek_record = await trek.queries.add_trek(
        db, origin="testOrigin", destination="testDestination"
    )
    trek_id = trek_record["id"]
    await trek.queries.add_trek(
        db, origin="testOrigin2", destination="testDestination2"
    )
    users_in = [{"trek_id": trek_id, "user_id": user_id} for user_id in user_ids[0:2]]
    await trek.queries.add_trek_users(db, users_in)
    return trek_id


@test("test_add")
async def test_add(db=connect_db):
    user_ids = await add_users(db)
    response = await client.post(
        "/trek/",
        json={
            "origin": "testOrigin",
            "destination": "testDestination",
            "waypoints": [
                [10.671114, 59.332889, 18.35],
                [10.671664, 59.333243, 18.31],
                [10.671857, 59.333329, 18.32],
                [10.672099, 59.333292, 17.51],
            ],
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
            "destination": "testDestination",
            "ongoing": False,
            "started_at": None,
        }
    ]
    assert res == exp

    res = await all_rows_in_table(db, "trek_user")
    exp = [{"trek_id": 1, "user_id": 1}, {"trek_id": 1, "user_id": 2}]
    assert res == exp

    res = await all_rows_in_table(db, "waypoint")
    exp = [
        {
            "id": 1,
            "trek_id": 1,
            "lat": 10.671114,
            "lon": 59.332889,
            "elevation": 18.35,
            "distance": 0.0,
        },
        {
            "id": 2,
            "trek_id": 1,
            "lat": 10.671664,
            "lon": 59.333243,
            "elevation": 18.31,
            "distance": 72.11886064837488,
        },
        {
            "id": 3,
            "trek_id": 1,
            "lat": 10.671857,
            "lon": 59.333329,
            "elevation": 18.32,
            "distance": 95.44853837588332,
        },
        {
            "id": 4,
            "trek_id": 1,
            "lat": 10.672099,
            "lon": 59.333292,
            "elevation": 17.51,
            "distance": 122.52108499023316,
        },
    ]
    assert res == exp


@test("test_get")
async def test_get(db=connect_db):
    user_ids = await add_users(db)
    trek_id = await add_treks(db, user_ids)

    response = await client.get(f"/trek/{trek_id}")
    res = response.json()
    exp = {
        "id": 1,
        "origin": "testOrigin",
        "destination": "testDestination",
        "ongoing": False,
        "started_at": None,
        "users": [1, 2],
    }
    assert res == exp
    assert response.status_code == 200


@test("test_delete")
async def test_delete(db=connect_db):
    user_ids = await add_users(db)
    trek_id = await add_treks(db, user_ids)
    # TODO: add waypoints
    response = await client.delete(f"/trek/{trek_id}")
    assert response.status_code == 200
    # res = await all_rows_in_table(db, "waypoint")
    res = await all_rows_in_table(db, "trek_user")
    assert res == []
    res = await all_rows_in_table(db, "trek")
    exp = [
        {
            "id": 2,
            "origin": "testOrigin2",
            "destination": "testDestination2",
            "ongoing": False,
            "started_at": None,
        }
    ]
    assert res == exp
