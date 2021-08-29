from databases import Database
from ward import test

from tests.conftest import all_rows_in_table, client, connect_db


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


@test("test_add_user ")
async def test_add_user(db=connect_db):
    response = await client.post("/user/", json={"name": "testUser1"})
    assert response.json() == {"user_id": 1}
    assert response.status_code == 200
    res = await all_rows_in_table(db, "user_")
    exp = [{"id": 1, "name_": "testUser1", "is_admin": False}]
    assert res == exp


@test("test_get_user")
async def test_get_user(db=connect_db):
    user_ids = await _preadd_users(db)
    response = await client.get(f"/user/{user_ids[0]}")
    res = response.json()
    exp = {"id": 1, "name": "testName1", "is_admin": False}
    assert res == exp


@test("test_get_all_users")
async def test_get_all_users(db=connect_db):
    await _preadd_users(db)
    response = await client.get("/user/")
    res = response.json()
    exp = [
        {"name": "testName1", "id": 1, "is_admin": False},
        {"name": "testName2", "id": 2, "is_admin": False},
        {"name": "testName3", "id": 3, "is_admin": False},
    ]
    assert res == exp
