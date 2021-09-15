from databases import Database
from ward import test

from tests.conftest import connect_db
from trek.trackers.fitbit_ import FitbitService


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


def fake_token(user_id: int) -> dict:
    return {
        "user_id": f"fitbit_id{user_id}",
        "access_token": f"access_token{user_id}",
        "refresh_token": f"refresh_token{user_id}",
        "expires_at": 1573921366.6757,
    }


@test("test_persist_token ")
async def test_persist_token(db=connect_db):
    user_ids = await _preadd_users(db)
    token = fake_token(user_id=user_ids[0])
    await FitbitService.persist_token(db=db, user_id=user_ids[0], token=token)
    tokens = await db.fetch_all("select * from user_token")
    assert len(tokens) == 1
    token = dict(tokens[0])
    exp = {
        "tracker": "fitbit",
        "user_id_": 1,
        "token": {
            "access_token": "access_token1",
            "expires_at": 1573921366.6757,
            "refresh_token": "refresh_token1",
            "user_id": "fitbit_id1",
        },
    }
    assert token == exp
