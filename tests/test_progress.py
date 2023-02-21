import typing as t

import pendulum
import pyarrow as pa
from ward import test

from tests.testing_utils import test_db
from trek.core.progress import progress
from trek.database import Database, trek_user_schema, user_schema, waypoint_schema
from trek.models import Id, Leg, Location, Trek, TrekUser, User, Waypoint


def example_waypoints(trek_id: Id, leg_id: Id) -> list[dict]:
    return [
        {
            "id": "waypoint1",
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": 0.1,
            "lon": 0.0,
            "distance": 0.0,
        },
        {
            "id": "waypoint2",
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": 0.2,
            "lon": 0.0,
            "distance": 11057.43,
        },
        {
            "id": "waypoint3",
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": 0.3,
            "lon": 0.0,
            "distance": 22114.86,
        },
        {
            "id": "waypoint4",
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": 0.4,
            "lon": 0.0,
            "distance": 33172.29,
        },
    ]


def _preadd_users(db: Database) -> list[Id]:
    user_records = [{"id": db.make_id()} for _ in range(3)]
    table = pa.Table.from_pylist(user_records, schema=user_schema)
    db.save_table(User, table)
    user_ids = [user["id"] for user in user_records]
    return user_ids


def _preadd_treks(
    db: Database, user_ids: list[Id], add_location=True, location_added_at=None
) -> tuple[Id, Id]:
    trek_id = db.make_id()
    trek_record = {
        "id": trek_id,
        "is_active": True,
        "owner_id": user_ids[0],
        "progress_at_hour": 12,
        "progress_at_tz": "UTC",
    }
    db.append_record(Trek, trek_record)

    leg_id = db.make_id()
    leg_record = {
        "id": leg_id,
        "trek_id": trek_id,
        "destination": "testDestination",
        "added_at": pendulum.datetime(2000, 2, 5, 12, 30, 5),
        "added_by": user_ids[0],
        "is_finished": False,
    }
    db.append_record(Leg, leg_record)

    waypoint_records = example_waypoints(trek_id, leg_id)
    waypoints_table = pa.Table.from_pylist(waypoint_records, schema=waypoint_schema)
    db.save_table(Waypoint, waypoints_table)

    if add_location:
        location_record = {
            "trek_id": trek_id,
            "leg_id": leg_id,
            "latest_waypoint": waypoint_records[1]["id"],
            "added_at": location_added_at,
            "address": "my_address",
            "lat": 0.2,
            "lon": 0.0,
            "distance": 11057.43,
        }
        db.append_record(Location, location_record)

    other_trek_id = db.make_id()
    other_trek_record = {
        "id": other_trek_id,
        "is_active": True,
        "owner_id": user_ids[1],
        "progress_at_hour": 18,
        "progress_at_tz": "UTC",
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
    other_waypoint_records = example_waypoints(other_trek_id, other_leg_id)
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
    return trek_id, leg_id


@test("treks_to_update_1_days_since_last_update")
def test_treks_to_update_1_days_since_last_update(db=test_db):
    user_ids = _preadd_users(db)
    trek_id, _ = _preadd_treks(
        db, user_ids, location_added_at=pendulum.datetime(2000, 2, 4)
    )
    date = pendulum.datetime(2000, 2, 5, hour=12)
    res = list(progress._get_treks_to_update(db, date))
    assert len(res) == 1
    trek, leg = res[0]
    trek_exp = {
        "id": "00000000000000000000000000000003",
        "is_active": True,
        "output_to": None,
        "owner_id": "00000000000000000000000000000000",
        "progress_at_hour": 12,
        "progress_at_tz": "UTC",
    }

    # pandas' to_records does not convert pandas.TimeStamp to dt.datetime
    leg["added_at"] = pendulum.instance(leg["added_at"].to_pydatetime())  # type: ignore

    leg_exp = {
        "added_at": pendulum.datetime(2000, 2, 5, 12, 30, 5),
        "added_by": "00000000000000000000000000000000",
        "id": "00000000000000000000000000000004",
        "is_finished": False,
        "trek_id": "00000000000000000000000000000003",
    }
    assert trek == trek_exp
    assert leg == leg_exp


@test("treks_to_update_1_hour_since_last_update")
def test_treks_to_update_1_hour_since_last_update(db=test_db):
    user_ids = _preadd_users(db)
    _preadd_treks(
        db, user_ids, location_added_at=pendulum.datetime(2000, 2, 5, hour=11)
    )
    date = pendulum.datetime(2000, 2, 5, hour=12)
    res = list(progress._get_treks_to_update(db, date))
    assert len(res) == 0


@test("treks_to_update_no_locations")
def test_treks_to_update_no_locations(db=test_db):
    user_ids = _preadd_users(db)
    trek_id, leg_id = _preadd_treks(db, user_ids, add_location=False)
    date = pendulum.datetime(2000, 2, 5, hour=12)
    res = list(progress._get_treks_to_update(db, date))
    assert len(res) == 1
    assert len(res) == 1
    trek, leg = res[0]
    trek_exp = {
        "id": trek_id,
        "is_active": True,
        "output_to": None,
        "owner_id": "00000000000000000000000000000000",
        "progress_at_hour": 12,
        "progress_at_tz": "UTC",
    }
    # pandas' to_records does not convert pandas.TimeStamp to dt.datetime
    leg["added_at"] = pendulum.instance(leg["added_at"].to_pydatetime())  # type: ignore

    leg_exp = {
        "added_at": pendulum.datetime(2000, 2, 5, 12, 30, 5),
        "added_by": "00000000000000000000000000000000",
        "id": leg_id,
        "is_finished": False,
        "trek_id": "00000000000000000000000000000003",
    }

    assert trek == trek_exp
    assert leg == leg_exp


def fake_upload_func(*args, **kwargs):
    return "upload_res"


def fake_location_apis_func(*args, **kwargs):
    return ("address", "country", "photo", "map_url", "poi")


def fake_mapping_func(*args, **kwargs):
    return "map_res"


@test("execute_daily_progression_no_last_location")
def test_execute_daily_progression_no_last_location(db=test_db):
    user_ids = _preadd_users(db)
    trek_id, leg_id = _preadd_treks(db, user_ids, add_location=False)
    date = pendulum.datetime(2000, 2, 5, 12, 30, 5)
    users_progress: t.Any = [
        {"step": {"amount": 5000}},
        {"step": {"amount": 5000}},
        {"step": {"amount": 5000}},
    ]
    res = progress._execute_daily_progression(
        db,
        trek_id,
        leg_id,
        date,
        users_progress,
        fake_upload_func,
        fake_location_apis_func,
        fake_mapping_func,
    )
    assert res is not None
    locaction, new_achievement = res
    assert new_achievement is None
    exp = {
        "trek_id": "00000000000000000000000000000003",
        "leg_id": "00000000000000000000000000000004",
        "lat": 0.2017299,
        "lon": 0.0,
        "distance": 11250.0,  # distance is 15 000 * 0.75 (STRIDE)
        "added_at": pendulum.datetime(2000, 2, 5, 12, 30, 5),
        "is_last_in_leg": False,
        "latest_waypoint": "waypoint2",
        "address": "address",
        "country": "country",
        "is_new_country": False,
        "gmap_url": "map_url",
        "traversal_map_url": "map_res",
        "poi": "poi",
        "photo_url": "photo",
        "achievements": None,
        "factoid": None,
    }
    assert locaction == exp


@test("execute_daily_progression")
def test_execute_daily_progression(db=test_db):
    user_ids = _preadd_users(db)
    trek_id, leg_id = _preadd_treks(db, user_ids, add_location=True)
    date = pendulum.datetime(2000, 2, 5, 12, 30, 5)
    users_progress: t.Any = [
        {"step": {"amount": 5000}},
        {"step": {"amount": 5000}},
        {"step": {"amount": 5000}},
    ]
    res = progress._execute_daily_progression(
        db,
        trek_id,
        leg_id,
        date,
        users_progress,
        fake_upload_func,
        fake_location_apis_func,
        fake_mapping_func,
    )
    assert res is not None
    locaction, new_achievement = res
    assert new_achievement is None

    exp = {
        "trek_id": "00000000000000000000000000000003",
        "leg_id": "00000000000000000000000000000004",
        "lat": 0.3017299,
        "lon": 0.0,
        "distance": 22307.43,
        "added_at": pendulum.datetime(2000, 2, 5, 12, 30, 5),
        "is_last_in_leg": False,
        "latest_waypoint": "waypoint3",
        "address": "address",
        "country": "country",
        "is_new_country": False,
        "gmap_url": "map_url",
        "traversal_map_url": "map_res",
        "poi": "poi",
        "photo_url": "photo",
        "achievements": None,
        "factoid": None,
    }
    assert locaction == exp


# @test("treks_to_update_1_days_since_last_10h")
# def test_treks_to_update_1_days_since_last_10h(db=test_db):
#     user_ids = _preadd_users(db)
#     trek_id, leg_id = _preadd_treks(db, user_ids)
#     queries.add_location(
#         db,
#         trek_id=trek_id,
#         leg_id=leg_id,
#         added_at=pendulum.date(2000, 2, 7),
#         address="my_address",
#     )
#     now = dt.datetime(2000, 2, 9, 10, 0, 0)
#     res = queries.treks_to_update(db, now=now)
#     assert res == []


# @test("treks_to_update_0_days_since_last_20h")
# def test_treks_to_update_0_days_since_last_20h(db=test_db):
#     user_ids = _preadd_users(db)
#     trek_id, leg_id = _preadd_treks(db, user_ids)
#     queries.add_location(
#         db,
#         trek_id=trek_id,
#         leg_id=leg_id,
#         added_at=pendulum.date(2000, 2, 8),
#         address="my_address",
#     )
#     now = dt.datetime(2000, 2, 9, 20, 0, 0)
#     res = queries.treks_to_update(db, now=now)
#     assert res == []


# @test("treks_to_update_2_days_since_last_10h")
# def test_treks_to_update_2_days_since_last_10h(db=test_db):
#     user_ids = _preadd_users(db)
#     trek_id, leg_id = _preadd_treks(db, user_ids)
#     queries.add_location(
#         db,
#         trek_id=trek_id,
#         leg_id=leg_id,
#         added_at=pendulum.date(2000, 2, 6),
#         address="my_address",
#     )
#     now = dt.datetime(2000, 2, 9, 10, 0, 0)
#     res = queries.treks_to_update(db, now=now)
#     assert len(res) == 1
#     exp = {
#         "trek_id": 1,
#         "leg_id": 1,
#         "most_recent_location_date": pendulum.date(2000, 2, 6),
#         "execute_yesterdays_progress": False,
#     }
#     assert dict(res[0]) == exp


# @test("treks_to_update_never_updated")
# def test_treks_to_update_never_updated(db=test_db):
#     ...
