import datetime as dt

from freezegun import freeze_time
import pendulum
import pyarrow as pa
import pyarrow.compute as pc
from ward import fixture, raises, test

from tests.testing_utils import test_db
from trek import exceptions as exc
from trek.core import crud
from trek.database import Database, trek_user_schema, user_schema, waypoint_schema
from trek.models import Id, Leg, Trek, TrekUser, User, Waypoint

# @test("flake")
# def test_flake(db: Database = test_db):
#     from tests.testing_utils import TestDatabase
#     import tempfile
#     from pathlib import Path

#     for i in range(100):
#         with tempfile.TemporaryDirectory() as temp_dir:
#             db = TestDatabase(Path(temp_dir))

#             trek_record = {
#                 "id": db.make_id(),
#                 "is_active": False,
#                 "owner_id": db.make_id(),
#             }
#             db.append_record(Trek, trek_record)

#             other_trek_record = {
#                 "id": db.make_id(),
#                 "is_active": False,
#                 "owner_id": db.make_id(),
#             }
#             db.append_record(Trek, other_trek_record)

#             treks = db.load_table(Trek).to_pylist()
#             sort = [
#                 {
#                     "id": "00000000000000000000000000000000",
#                     "is_active": False,
#                     "owner_id": "00000000000000000000000000000001",
#                     "progress_at_hour": None,
#                     "progress_at_tz": None,
#                 },
#                 {
#                     "id": "00000000000000000000000000000002",
#                     "is_active": False,
#                     "owner_id": "00000000000000000000000000000003",
#                     "progress_at_hour": None,
#                     "progress_at_tz": None,
#                 },
#             ]
#             assert treks == sort
#             # if treks != sort:
#             #     print(i)
#             #     breakpoint()
#             #     break
#             #     1 + 1
#     # 1  /  0


@fixture
def freeze():
    with freeze_time("2012-01-14"):
        yield


def example_waypoints(db: Database, trek_id: Id, leg_id: Id) -> list[Waypoint]:
    return [
        {
            "id": db.make_id(),
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": 10.671114,
            "lon": 59.332889,
            "distance": 0.0,
        },
        {
            "id": db.make_id(),
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": 10.671664,
            "lon": 59.333243,
            "distance": 72.11886064837488,
        },
        {
            "id": db.make_id(),
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": 10.671857,
            "lon": 59.333329,
            "distance": 95.44853837588332,
        },
        {
            "id": db.make_id(),
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": 10.672099,
            "lon": 59.333292,
            "distance": 122.52108499023316,
        },
    ]


def _preadd_users(db: Database) -> list[Id]:
    user_records = [{"id": db.make_id()} for _ in range(3)]
    table = pa.Table.from_pylist(user_records, schema=user_schema)
    db.save_table(User, table)
    user_ids = [user["id"] for user in user_records]
    return user_ids


def _preadd_treks(
    db: Database, user_ids: list[Id], leg_is_finished=False, trek_is_active=False
) -> Id:
    trek_id = db.make_id()
    trek_record = {
        "id": trek_id,
        "is_active": trek_is_active,
        "owner_id": user_ids[0],
    }
    db.append_record(Trek, trek_record)

    leg_record = {
        "id": db.make_id(),
        "trek_id": trek_id,
        "destination": "testDestination",
        "added_at": pendulum.datetime(2000, 2, 5, 12, 30, 5),
        "added_by": user_ids[0],
        "is_finished": leg_is_finished,
    }
    leg_id = leg_record["id"]
    db.append_record(Leg, leg_record)

    waypoint_records = example_waypoints(db, trek_id, leg_id)
    waypoints_table = pa.Table.from_pylist(waypoint_records, schema=waypoint_schema)
    db.save_table(Waypoint, waypoints_table)

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


@test("test_add_trek")
def test_add_trek(db=test_db, _=freeze):
    request = crud.AddTrekRequest(
        progress_at_hour=12,
        progress_at_tz="CET",
        output_to="discord",
        polyline="skc`AapciJiw@oyBmBeA",
    )
    user_id = db.make_id()
    response = crud.add_trek(request, db, user_id)
    assert response.dict() == {"trek_id": "00000000000000000000000000000001"}

    treks = db.load_table(Trek).to_pylist()
    treks_exp = [
        {
            "id": "00000000000000000000000000000001",
            "is_active": False,
            "owner_id": "00000000000000000000000000000000",
            "progress_at_hour": 12,
            "progress_at_tz": "CET",
            "output_to": "discord",
        },
    ]
    assert treks == treks_exp

    trek_users = db.load_table(TrekUser).to_pylist()
    trek_users_exp = [
        {
            "trek_id": "00000000000000000000000000000001",
            "user_id": "00000000000000000000000000000000",
            "added_at": dt.datetime(2012, 1, 14, 0, 0),  # tzinfo=dt.timezone.utc,
            "color": "#2cb",
        },
    ]

    assert trek_users == trek_users_exp

    legs = db.load_table(Leg).to_pylist()
    assert legs == [
        {
            "id": "00000000000000000000000000000002",
            "trek_id": "00000000000000000000000000000001",
            "added_at": dt.datetime(2012, 1, 14),
            "added_by": "00000000000000000000000000000000",
            "is_finished": False,
        }
    ]


@test("test_add_leg")
def test_add_leg(db=test_db, _=freeze):
    user_ids = _preadd_users(db)
    user_id = user_ids[1]
    trek_id = _preadd_treks(db, user_ids, leg_is_finished=True)

    assert db.load_table(Leg).num_rows == 2

    request = crud.AddLegRequest(polyline="skc`AapciJiw@oyBmBeA")
    response = crud.add_leg(trek_id, request, db, user_id).dict()
    assert response == {"leg_id": "0000000000000000000000000000000f"}

    leg_records = db.load_table(Leg).to_pylist()
    assert len(leg_records) == 3
    assert leg_records[-1] == {
        "added_at": dt.datetime(2012, 1, 14, 0, 0),
        "added_by": "00000000000000000000000000000001",
        "id": "0000000000000000000000000000000f",
        "is_finished": False,
        "trek_id": "00000000000000000000000000000003",
    }

    waypoint_records = db.load_table(
        Waypoint,
        filter=(
            (pc.field("trek_id") == pc.scalar(trek_id))
            & (pc.field("leg_id") == pc.scalar(response["leg_id"]))
        ),
    ).to_pylist()
    assert waypoint_records == [
        {
            "id": "00000000000000000000000000000010",
            "trek_id": "00000000000000000000000000000003",
            "leg_id": "0000000000000000000000000000000f",
            "lat": 10.6721,
            "lon": 59.33329,
            "distance": 0.0,
        },
        {
            "id": "00000000000000000000000000000011",
            "trek_id": "00000000000000000000000000000003",
            "leg_id": "0000000000000000000000000000000f",
            "lat": 10.68111,
            "lon": 59.35289,
            "distance": 2364.62,
        },
        {
            "id": "00000000000000000000000000000012",
            "trek_id": "00000000000000000000000000000003",
            "leg_id": "0000000000000000000000000000000f",
            "lat": 10.68166,
            "lon": 59.35324,
            "distance": 2436.5,
        },
    ]


@test("test_assert_no_unfinished_leg")
def test_assert_no_unfinished_leg(db=test_db):
    user_ids = _preadd_users(db)
    _preadd_treks(db, user_ids)
    leg_table = db.load_table(Leg)
    with raises(exc.ServerException) as ctx:
        crud._assert_no_unfinished_leg(leg_table)
    assert ctx.raised.model.dict() == {
        "detail": "Trek has unfinished leg",
        "error_code": "E101Error",
        "message": "Server error occured",
        "status_code": 400,
    }


@test("test_assert_is_next_leg_adder_fails")
def test_assert_is_next_leg_adder_fails(db=test_db):
    user_ids = _preadd_users(db)
    user_id = user_ids[0]
    trek_id = _preadd_treks(db, user_ids)
    leg_table = db.load_table(Leg, filter=pc.field("trek_id") == pc.scalar(trek_id))
    trek_users = db.load_records(
        TrekUser, filter=pc.field("trek_id") == pc.scalar(trek_id)
    )
    with raises(exc.ServerException) as ctx:
        crud._assert_is_next_leg_adder(trek_users, leg_table, user_id)
    assert ctx.raised.model.dict() == {
        "detail": "User is not in line to add leg",
        "error_code": "E101Error",
        "message": "Server error occured",
        "status_code": 400,
    }


@test("test_assert_is_next_leg_adder")
def test_assert_is_next_leg_adder(db=test_db):
    user_ids = _preadd_users(db)
    user_id = user_ids[1]
    trek_id = _preadd_treks(db, user_ids)
    leg_table = db.load_table(Leg, filter=pc.field("trek_id") == pc.scalar(trek_id))
    trek_users = db.load_records(
        TrekUser, filter=pc.field("trek_id") == pc.scalar(trek_id)
    )
    crud._assert_is_next_leg_adder(trek_users, leg_table, user_id)


@test("test_assert_waypoints_connect")
def test_assert_waypoints_connect(db=test_db):
    user_ids = _preadd_users(db)
    trek_id = _preadd_treks(db, user_ids)
    leg_table = db.load_table(Leg, filter=pc.field("trek_id") == pc.scalar(trek_id))
    new_waypoints = [(1.672099, 59.333292, 17.51), (2.672099, 59.333292, 17.51)]
    with raises(exc.ServerException) as ctx:
        crud._assert_waypoints_connect(db, leg_table, trek_id, new_waypoints)
    assert ctx.raised.model.dict() == {
        "detail": "Leg does not start where last ended - (10, 59) vs (1, 59)",
        "error_code": "E101Error",
        "message": "Server error occured",
        "status_code": 400,
    }


@test("test_get")
def test_get(db=test_db):
    user_ids = _preadd_users(db)
    trek_id = _preadd_treks(db, user_ids)
    user_id = user_ids[0]
    response = crud.get_trek(trek_id, db, user_id)
    trek_record = response.dict()
    exp = {
        "can_add_leg": False,
        "current_location": None,
        "is_active": False,
        "is_owner": True,
        "legs": [
            {
                "added_at": dt.datetime(2000, 2, 5, 12, 30, 5),
                "added_by": "00000000000000000000000000000000",
                "id": "00000000000000000000000000000004",
                "is_finished": False,
                "trek_id": "00000000000000000000000000000003",
            },
        ],
        "users": [
            "00000000000000000000000000000000",
            "00000000000000000000000000000001",
        ],
    }
    assert trek_record == exp


@test("test_delete")
def test_delete(db=test_db):
    user_ids = _preadd_users(db)
    user_id = user_ids[0]
    trek_id = _preadd_treks(db, user_ids)
    assert db.load_table(Trek).num_rows == 2
    assert db.load_table(Leg).num_rows == 2
    assert db.load_table(Waypoint).num_rows == 8
    assert db.load_table(TrekUser).num_rows == 2

    crud.delete_trek(trek_id, db, user_id)

    assert db.load_table(Trek).num_rows == 1
    assert db.load_table(Leg).num_rows == 1
    assert db.load_table(Waypoint).num_rows == 4
    assert db.load_table(TrekUser).num_rows == 2


@test("test_generate_invite")
def test_generate_invite(db=test_db):
    user_ids = _preadd_users(db)
    user_id = user_ids[0]
    trek_id = _preadd_treks(db, user_ids)
    response = crud.generate_trek_invite(trek_id, user_id, db)
    res = response.dict()
    assert "invite_id" in res
    assert len(res["invite_id"]) == 188
    decrypted_trek_id = crud._decrypt_id(res["invite_id"])
    assert trek_id == decrypted_trek_id


@test("test_add_user_to_trek")
def test_add_user_to_trek(db=test_db, _=freeze):
    user_ids = _preadd_users(db)
    user_id = user_ids[-1]
    trek_id = _preadd_treks(db, user_ids)
    encrypted_trek_id = crud._encrypt_id(trek_id)
    trek_users_before = db.load_table(
        TrekUser, filter=pc.field("trek_id") == pc.scalar(trek_id)
    )
    assert trek_users_before.num_rows == 2

    crud.add_user_to_trek(encrypted_trek_id, db, user_id)

    trek_users = db.load_table(
        TrekUser, filter=pc.field("trek_id") == pc.scalar(trek_id)
    ).sort_by("added_at")
    assert trek_users.num_rows == 3

    res = trek_users.to_pylist()[-1]
    exp = {
        "added_at": dt.datetime(2012, 1, 14, 0, 0),
        "trek_id": trek_id,
        "user_id": user_id,
        "color": "#639",
    }
    assert res == exp


@test("test_activate_trek")
def test_activate_trek(db=test_db):
    user_ids = _preadd_users(db)
    trek_id = _preadd_treks(db, user_ids)
    user_id = user_ids[0]
    trek_records_before = db.load_table(Trek).to_pylist()

    assert trek_records_before == [
        {
            "id": "00000000000000000000000000000003",
            "is_active": False,
            "owner_id": "00000000000000000000000000000000",
            "progress_at_hour": None,
            "progress_at_tz": None,
            "output_to": None,
        },
        {
            "id": "00000000000000000000000000000009",
            "is_active": False,
            "owner_id": "00000000000000000000000000000001",
            "progress_at_hour": None,
            "progress_at_tz": None,
            "output_to": None,
        },
    ]

    crud.activate_trek(trek_id, user_id, db)

    trek_records = db.load_table(Trek).to_pylist()

    assert trek_records == [
        {
            "id": "00000000000000000000000000000003",
            "is_active": True,
            "owner_id": "00000000000000000000000000000000",
            "progress_at_hour": None,
            "progress_at_tz": None,
            "output_to": None,
        },
        {
            "id": "00000000000000000000000000000009",
            "is_active": False,
            "owner_id": "00000000000000000000000000000001",
            "progress_at_hour": None,
            "progress_at_tz": None,
            "output_to": None,
        },
    ]


@test("test_deactivate_trek")
def test_deactivate_trek(db=test_db):
    user_ids = _preadd_users(db)
    trek_id = _preadd_treks(db, user_ids, trek_is_active=True)
    user_id = user_ids[0]
    trek_records_before = db.load_table(Trek).to_pylist()

    assert trek_records_before == [
        {
            "id": "00000000000000000000000000000003",
            "is_active": True,
            "owner_id": "00000000000000000000000000000000",
            "progress_at_hour": None,
            "progress_at_tz": None,
            "output_to": None,
        },
        {
            "id": "00000000000000000000000000000009",
            "is_active": False,
            "owner_id": "00000000000000000000000000000001",
            "progress_at_hour": None,
            "progress_at_tz": None,
            "output_to": None,
        },
    ]

    crud.deactivate_trek(trek_id, user_id, db)

    trek_records = db.load_table(Trek).to_pylist()

    assert trek_records == [
        {
            "id": "00000000000000000000000000000003",
            "is_active": False,
            "owner_id": "00000000000000000000000000000000",
            "progress_at_hour": None,
            "progress_at_tz": None,
            "output_to": None,
        },
        {
            "id": "00000000000000000000000000000009",
            "is_active": False,
            "owner_id": "00000000000000000000000000000001",
            "progress_at_hour": None,
            "progress_at_tz": None,
            "output_to": None,
        },
    ]
