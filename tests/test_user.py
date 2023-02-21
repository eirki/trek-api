import typing as t

from fastapi_jwt_auth import AuthJWT
import pendulum
import pyarrow as pa
from ward import test

from tests.testing_utils import test_db
from trek import utils
from trek.core import user
from trek.core.trackers import tracker_utils
from trek.database import (
    Database,
    trek_user_schema,
    user_schema,
    user_token_schema,
    waypoint_schema,
)
from trek.models import Id, Leg, Trek, TrekUser, User, UserToken, Waypoint


class FakeService:
    name = "my-fake-service"
    auth_url = "https://authorization.url"

    def __init__(self, tracker_user_id=None):
        self._tracker_user_id = tracker_user_id

    def authorization_url(self) -> str:
        return self.auth_url

    def token(self, code: str) -> dict:
        return {"token": "my_token " + code}

    def tracker_user_id_from_token(self, token: dict) -> str:
        return self._tracker_user_id

    @property
    def User(self):
        return FakeUser


class FakeUser:
    def __init__(self, db: Database, user_id: Id, *args, **kwargs):
        self.db = db
        self.user_id = user_id

    def persist_token(self, token: dict):
        tracker_utils.persist_token(
            db=self.db,
            token=token,
            user_id=self.user_id,
            tracker_name="fitbit",
            tracker_user_id=Id("tracker_user_id"),
        )

    def user_name(self):
        return "My fake user name"


def _preadd_users(db: Database) -> list[Id]:
    user_records = [{"id": db.make_id()} for _ in range(3)]
    table = pa.Table.from_pylist(user_records, schema=user_schema)
    db.save_table(User, table)
    user_ids = [user["id"] for user in user_records]
    return user_ids


def _preadd_treks(db: Database, user_ids: list[str]) -> str:
    trek_id = db.make_id()
    trek_record = {
        "id": trek_id,
        "is_active": False,
        "owner_id": user_ids[0],
    }
    db.append_record(Trek, trek_record)

    leg_record = {
        "id": db.make_id(),
        "trek_id": trek_id,
        "destination": "testDestination",
        "added_at": pendulum.datetime(2000, 2, 5, 12, 30, 5),
        "added_by": user_ids[0],
        "is_finished": False,
    }
    db.append_record(Leg, leg_record)

    other_trek_id = db.make_id()
    other_trek_record = {
        "id": other_trek_id,
        "is_active": False,
        "owner_id": user_ids[1],
    }
    db.append_record(Trek, other_trek_record)
    other_leg_id = db.make_id()
    other_leg_record = {
        "id": other_leg_id,
        "trek_id": other_trek_id,
        "destination": "testDestination",
        "added_at": pendulum.datetime(2000, 2, 5, 12, 30, 5),
        "added_by": user_ids[1],
        "is_finished": False,
    }
    db.append_record(Leg, other_leg_record)
    other_waypoint_records = example_waypoints(db, other_trek_id, other_leg_id)
    other_waypoints_table = pa.Table.from_pylist(
        other_waypoint_records, schema=waypoint_schema
    )
    db.save_table(Waypoint, other_waypoints_table)

    trek_user_records = [
        {
            "trek_id": trek_id,
            "user_id": user_id,
            "added_at": pendulum.datetime(2000, 2, 5, 12, 30, 5),
        }
        for user_id in user_ids[0:2]
    ]
    trek_users_table = pa.Table.from_pylist(trek_user_records, schema=trek_user_schema)
    db.save_table(TrekUser, trek_users_table)
    return trek_id


@test("test_add_user ")
def test_add_user(db=test_db):
    user_id = Id("00000000000000000000000000000000")
    user._add_user(
        db,
        user_id=user_id,
        tracker_name="fitbit",
        user_name="my_user_name",
    )
    assert user_id == "00000000000000000000000000000000"
    user_records = db.load_table(User).to_pylist()
    exp = [
        {
            "active_tracker": "fitbit",
            "id": "00000000000000000000000000000000",
            "is_admin": False,
            "name": "my_user_name",
        },
    ]
    assert user_records == exp


@test("test_auth ")
def test_auth():
    service: t.Any = FakeService()
    redirect_url = "https://www.redirect.me"
    authorize_rseponse = user.authorize(service, redirect_url)
    res = authorize_rseponse.dict()
    assert "auth_url" in res
    assert res["auth_url"].startswith(FakeService.auth_url)


@test("test_redirect_new_user ")
def test_redirect_new_user(db=test_db):
    service: t.Any = FakeService()
    state = utils.encode_dict({"frontend_redirect_url": "https://www.redirect.me"})
    code = "thisisacode"
    Authorize = AuthJWT()
    res = user.handle_redirect(
        service=service, code=code, state=state, db=db, Authorize=Authorize
    )
    assert res.startswith("https://www.redirect.me")
    user_records = db.load_table(User).to_pylist()
    assert user_records == [
        {
            "active_tracker": "my-fake-service",
            "id": "00000000000000000000000000000000",
            "is_admin": False,
            "name": "My fake user name",
        },
    ]
    user_token_records = db.load_table(UserToken).to_pylist()
    assert user_token_records == [
        {
            "token": '{"token": "my_token thisisacode"}',
            "tracker_name": "fitbit",
            "tracker_user_id": "tracker_user_id",
            "user_id": "00000000000000000000000000000000",
        },
    ]


def example_waypoints(db: Database, trek_id: Id, leg_id: Id) -> list[dict]:
    return [
        {
            "id": db.make_id(),
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": 10.671114,
            "lon": 59.332889,
            "elevation": 18.35,
            "distance": 0.0,
        },
        {
            "id": db.make_id(),
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": 10.671664,
            "lon": 59.333243,
            "elevation": 18.31,
            "distance": 72.11886064837488,
        },
        {
            "id": db.make_id(),
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": 10.671857,
            "lon": 59.333329,
            "elevation": 18.32,
            "distance": 95.44853837588332,
        },
        {
            "id": db.make_id(),
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": 10.672099,
            "lon": 59.333292,
            "elevation": 17.51,
            "distance": 122.52108499023316,
        },
    ]


@test("test_redirect_new_login_existing_user ")
def test_redirect_new_login_existing_user(db: Database = test_db):
    user_id = db.make_id()
    user_token_record = {
        "token": "my_old_token",
        "user_id": user_id,
        "tracker_name": "fitbit",
        "tracker_user_id": "my_tracker_user_id",
    }
    table = pa.Table.from_pylist([user_token_record], schema=user_token_schema)
    db.save_table(UserToken, table)
    service: t.Any = FakeService(tracker_user_id="my_tracker_user_id")
    state = utils.encode_dict(
        {"user_id": user_id, "frontend_redirect_url": "https://www.redirect.me"}
    )
    code = "thisisacode"
    Authorize = AuthJWT()
    res = user.handle_redirect(
        service=service, code=code, state=state, db=db, Authorize=Authorize
    )
    assert res.startswith("https://www.redirect.me")
    user_token_records = db.load_table(UserToken).to_pylist()
    assert user_token_records == [
        {
            "token": '{"token": "my_token thisisacode"}',
            "tracker_name": "fitbit",
            "tracker_user_id": "tracker_user_id",
            "user_id": "00000000000000000000000000000000",
        },
    ]


@test("test_redirect_new_tracker_existing_user ")
def test_redirect_new_tracker_existing_user(db: Database = test_db):
    user_id = db.make_id()
    user_token_record = {
        "token": "my_existing_token",
        "user_id": user_id,
        "tracker_name": "withings",
        "tracker_user_id": "my_tracker_user_id",
    }
    table = pa.Table.from_pylist([user_token_record], schema=user_token_schema)
    db.save_table(UserToken, table)
    service: t.Any = FakeService(tracker_user_id="my_tracker_user_id")
    state = utils.encode_dict({"frontend_redirect_url": "https://www.redirect.me"})
    code = "thisisacode"
    Authorize = AuthJWT()
    res = user.handle_redirect(
        service=service, code=code, state=state, db=db, Authorize=Authorize
    )
    assert res.startswith("https://www.redirect.me")
    user_token_records = db.load_table(UserToken).sort_by("user_id").to_pylist()
    assert user_token_records == [
        {
            "token": "my_existing_token",
            "tracker_name": "withings",
            "tracker_user_id": "my_tracker_user_id",
            "user_id": "00000000000000000000000000000000",
        },
        {
            "token": '{"token": "my_token thisisacode"}',
            "tracker_name": "fitbit",
            "tracker_user_id": "tracker_user_id",
            "user_id": "00000000000000000000000000000000",
        },
    ]


# @test("test_me")
# def test_me(db: Database = test_db):
#     user_ids = _preadd_users(db)
#     user_id = user_ids[1]
#     _preadd_treks(db, user_ids)
#     token = {
#         "user_id": "fb00000000000000000000000000000000",
#         "access_token": "access_token00000000000000000000000000000000",
#         "refresh_token": "refresh_token00000000000000000000000000000000",
#         "expires_at": 1573921366.6757,
#     }

#     user_token_record = {
#         "token": json.dumps(token),
#         "user_id": user_id,
#         "tracker_name": "fitbit",
#         "tracker_user_id": "my_tracker_user_id",
#     }
#     table = pa.Table.from_pylist([user_token_record], schema=user_token_schema)
#     db.save_table(UserToken, table)
#     res = user.me(db, user_id).dict()
#     assert res == {
#         "trackers": ["fitbit"],
#         "treks_owner_of": ["00000000000000000000000000000005"],
#         "treks_user_in": ["00000000000000000000000000000003"],
#         "user_id": "00000000000000000000000000000001",
#     }


# @test("is_authenticated")
# def test_is_authenticated(
#     # _=testing_utils.overide(testing_utils.auth_overrides(user_id=4))
# ):
#     response = await client.get("/user/is_authenticated")
#     assert response.status_code == 200
#     res = response.json()
#     exp = {"user_id": 4}
#     assert res == exp


# @test("not_is_authenticated")
# def test_not_is_authenticated():
#     response = await client.get("/user/is_authenticated")
#     assert response.status_code == 401
