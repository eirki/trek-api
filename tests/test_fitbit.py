from dataclasses import dataclass
import json

from databases import Database
from ward import test

from tests.conftest import connect_db
from trek.trackers.fitbit_ import FitbitUser


async def _preadd_users(db: Database) -> list[int]:
    sql = """insert into
            user_ (is_admin)
        values
            (:is_admin);
        """
    await db.execute_many(
        sql,
        values=[{"is_admin": False}] * 3,
    )
    user_ids = await db.fetch_all("select id from user_")
    assert len(user_ids) > 0
    as_int = [user["id"] for user in user_ids]
    assert all(isinstance(user_id, int) for user_id in as_int)
    return as_int


def fake_token(user_id: int) -> dict:
    return {
        "user_id": f"fb{user_id}",
        "access_token": f"access_token{user_id}",
        "refresh_token": f"refresh_token{user_id}",
        "expires_at": 1573921366.6757,
    }


@dataclass
class FakeService:
    db: Database
    user_id: int


@test("test_persist_token ")
async def test_persist_token(db=connect_db):
    user_ids = await _preadd_users(db)
    token_in = fake_token(user_id=user_ids[0])
    fake_service = FakeService(db=db, user_id=user_ids[0])
    await FitbitUser.persist_token(fake_service, token=token_in)  # type: ignore
    tokens = await db.fetch_all("select * from user_token")
    assert len(tokens) == 1
    token_table = dict(tokens[0])
    token_table["token"] = json.loads(token_table["token"])
    exp = {
        "token": {
            "access_token": "access_token1",
            "expires_at": 1573921366.6757,
            "refresh_token": "refresh_token1",
            "user_id": "fb1",
        },
        "tracker": "fitbit",
        "tracker_user_id": "fitbit_fb1",
        "user_id_": 1,
    }
    assert token_table == exp
