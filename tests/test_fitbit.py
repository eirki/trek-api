from dataclasses import dataclass
import json

import pyarrow as pa
from ward import test

from tests.testing_utils import test_db
from trek.core.trackers.fitbit_ import FitbitUser
from trek.database import Database, user_schema
from trek.models import Id, User, UserToken


def _preadd_users(db: Database) -> list[Id]:
    user_records = [{"id": db.make_id()} for _ in range(3)]
    table = pa.Table.from_pylist(user_records, schema=user_schema)
    db.save_table(User, table)
    user_ids = [user["id"] for user in user_records]
    return user_ids


def fake_token(user_id: Id) -> dict:
    return {
        "user_id": f"fb{user_id}",
        "access_token": f"access_token{user_id}",
        "refresh_token": f"refresh_token{user_id}",
        "expires_at": 1573921366.6757,
    }


@dataclass
class FakeService:
    db: Database
    user_id: Id


@test("test_persist_token ")
def test_persist_token(db: Database = test_db):
    user_ids = _preadd_users(db)
    user_id = user_ids[0]
    token_in = fake_token(user_id=user_id)
    fake_service = FakeService(db=db, user_id=user_id)
    FitbitUser.persist_token(fake_service, token=token_in)  # type: ignore
    user_tokens = db.load_records(UserToken)
    assert len(user_tokens) == 1
    token_record = user_tokens[0]
    token = json.loads(token_record.pop("token"))  # type: ignore
    exp = {
        "user_id": "00000000000000000000000000000000",
        "tracker_name": "fitbit",
        "tracker_user_id": "fitbit_fb00000000000000000000000000000000",
    }
    assert token_record == exp
    token_exp = {
        "user_id": "fb00000000000000000000000000000000",
        "access_token": "access_token00000000000000000000000000000000",
        "refresh_token": "refresh_token00000000000000000000000000000000",
        "expires_at": 1573921366.6757,
    }
    assert token == token_exp
