import json
import logging
import typing as t

import pendulum
import pyarrow as pa
import pyarrow.compute as pc

from trek.core.core_utils import get_next_leg_adder
from trek.core.output.output import outputters
from trek.core.output.output_utils import Outputter
from trek.core.progress import (
    achievements,
    factoids,
    location_apis,
    mapping,
    progress_utils,
)
from trek.core.progress.location_apis import LocationApisFunc
from trek.core.progress.mapping import MappingFunc
from trek.core.progress.progress_utils import UserProgress
from trek.core.progress.upload import UploadFunc, make_upload_f
from trek.core.trackers import trackers
from trek.database import Database, achievement_schema, step_schema
from trek.models import (
    Achievement,
    Id,
    Leg,
    Location,
    Step,
    Trek,
    TrekUser,
    User,
    UserToken,
    Waypoint,
)

log = logging.getLogger(__name__)


def _get_treks_to_update(
    db: Database, now: pendulum.DateTime
) -> t.Iterator[tuple[Trek, Leg]]:
    active_treks = db.load_records(Trek, filter=pc.field("is_active"))

    relevant_active_treks = [
        trek
        for trek in active_treks
        if now.in_timezone(trek["progress_at_tz"]).hour == trek["progress_at_hour"]
    ]

    if not relevant_active_treks:
        return
    relevant_active_treks_ids = [trek["id"] for trek in relevant_active_treks]
    legs_df = (
        db.load_table(Leg, filter=pc.field("trek_id").isin(relevant_active_treks_ids))
    ).to_pandas()
    latest_leg_idx = legs_df.groupby("trek_id")["added_at"].idxmax()
    latest_legs_df = legs_df.iloc[latest_leg_idx]
    latest_legs: list[Leg] = latest_legs_df.to_dict("records")
    if not latest_legs:
        return

    latest_leg_ids = [leg["id"] for leg in latest_legs]
    leg_for_trek_id = {leg["trek_id"]: leg for leg in latest_legs}

    latest_locations = (
        db.load_table(Location, filter=pc.field("leg_id").isin(latest_leg_ids))
        .group_by("trek_id")
        .aggregate([("added_at", "max")])
    ).to_pylist()
    latest_date_by_trek_id = {
        loc["trek_id"]: loc["added_at_max"] for loc in latest_locations
    }

    for trek in relevant_active_treks:
        last_updated_at = latest_date_by_trek_id.get(trek["id"])
        if last_updated_at is not None:
            # trek has locations
            update_at_tz = pendulum.datetime(
                now.year,
                now.month,
                now.day,
                trek["progress_at_hour"],
                tz=trek["progress_at_tz"],
            )
            if last_updated_at.day >= update_at_tz.day:
                continue
        leg = leg_for_trek_id[trek["id"]]
        yield trek, leg


def _users_in_trek(db: Database, trek_id: Id) -> list[TrekUser]:
    trek_users = db.load_records(
        TrekUser, filter=pc.field("trek_id") == pc.scalar(trek_id)
    )
    return trek_users


def _get_steps_for_single_user(
    db: Database, user_record: User, date: pendulum.Date
) -> int:
    active_tracker = user_record["active_tracker"]
    if active_tracker is None:
        log.info("no active tracker for user")
        return 0
    Service = trackers.name_to_service[active_tracker]
    try:
        token_record = db.load_records(
            UserToken,
            filter=(pc.field("user_id") == pc.scalar(user_record["id"]))
            & (pc.field("tracker_name") == pc.scalar(active_tracker)),
        )[0]
    except IndexError:
        log.info("could not find token for user")
        return 0
    try:
        user = Service.User(
            db=db,
            user_id=user_record["id"],
            token=json.loads(token_record["token"]),
        )
    except Exception as e:
        log.info(f"Failed to authenticate tracker user: {e}")
        return 0
    steps = user.steps(date, db)
    return steps


def _get_users_progress(
    db: Database,
    trek_id: Id,
    leg_id: Id,
    date: pendulum.Date,
    users: list[User],
    trek_users: list[TrekUser],
) -> list[UserProgress]:
    user_id_to_user_record = {user["id"]: user for user in users}
    users_progress: list[UserProgress] = []
    for trek_user in trek_users:
        user_id = trek_user["user_id"]
        # first from db
        # second from apis
        amount = _get_steps_for_single_user(db, user_id_to_user_record[user_id], date)

        step_record: Step = {
            "trek_id": trek_id,
            "leg_id": leg_id,
            "user_id": user_id,
            "taken_at": date,
            "amount": amount,
        }
        user_record = user_id_to_user_record[user_id]
        user_progress: UserProgress = {
            "user": user_record,
            "trek_user": trek_user,
            "step": step_record,
        }
        users_progress.append(user_progress)
    users_progress = sorted(
        users_progress, key=lambda prog: prog["step"]["amount"], reverse=True
    )
    return users_progress


def _save_users_progress(db: Database, users_progress: list[UserProgress]) -> None:
    new_step_records: list[Step] = [user["step"] for user in users_progress]
    steps_table = db.load_table(Step)
    record_table = pa.Table.from_pylist(new_step_records, schema=step_schema)
    merged_table = pa.concat_tables([steps_table, record_table])
    db.save_table(Step, merged_table)


def _most_recent_location(
    db: Database, trek_id: Id, leg_id: Id
) -> t.Optional[Location]:
    try:
        return (
            db.load_table(
                Location,
                filter=(pc.field("trek_id") == pc.scalar(trek_id))
                & (pc.field("leg_id") == pc.scalar(leg_id)),
            )
            .sort_by([("added_at", "descending")])
            .to_pylist()[0]
        )
    except IndexError:
        return None


def _load_waypoints_table(db: Database, trek_id: Id, leg_id: Id) -> pa.Table:
    return db.load_table(
        Waypoint,
        filter=(
            (pc.field("trek_id") == pc.scalar(trek_id))
            & (pc.field("leg_id") == pc.scalar(leg_id))
        ),
        columns=["lat", "lon", "distance", "id"],
    ).sort_by("distance")


def _point_at_distance(
    waypoints: pa.Table, distance: float
) -> tuple[tuple[float, float], Waypoint, bool]:
    has_passed_waypoint = pc.less_equal(waypoints.column("distance"), distance)

    passed_waypoints = waypoints.filter(has_passed_waypoint)
    log.info(f"{distance=}, {waypoints.num_rows=}, {passed_waypoints.num_rows=}")
    latest_waypoint = passed_waypoints.slice(
        offset=passed_waypoints.num_rows - 1, length=1
    ).to_pylist()[0]

    future_waypoints = waypoints.filter(pc.invert(has_passed_waypoint))

    try:
        next_waypoint = future_waypoints.slice(length=1).to_pylist()[0]
    except IndexError:
        finished = True
        current_lat = latest_waypoint["lat"]
        current_lon = latest_waypoint["lon"]
    else:
        finished = False
        remaining_dist = distance - latest_waypoint["distance"]
        current_lat, current_lon = progress_utils.point_between_waypoints(
            latest_waypoint, next_waypoint, remaining_dist
        )

    return (current_lat, current_lon), latest_waypoint, finished


def _get_days_distance_intervals(
    waypoints_table: pa.Table, from_distance: float, to_distance: float
) -> t.Iterator[tuple[float, float]]:
    incr_length = location_apis.poi_radius * 2
    for intermediate_distance in range(
        int(to_distance),
        int(min(from_distance + incr_length, from_distance)),
        -incr_length,
    ):
        inter_lat_lon, *_ = _point_at_distance(waypoints_table, intermediate_distance)
        yield inter_lat_lon


def _execute_daily_progression(
    db: Database,
    trek_id: Id,
    leg_id: Id,
    date: pendulum.Date,
    users_progress: list[UserProgress],
    upload_func: UploadFunc,
    location_apis_func: LocationApisFunc,
    mapping_func: MappingFunc,
) -> tuple[t.Optional[Location], t.Optional[list[Achievement]]]:
    steps_today = sum(user["step"]["amount"] for user in users_progress)
    log.info(f"{steps_today=}")
    if steps_today == 0:
        log.info("No steps")
        return None, None

    last_location = _most_recent_location(db, trek_id=trek_id, leg_id=leg_id)
    if last_location and last_location["is_last_in_leg"]:
        log.info("Leg is finished")
        return None, None
    progress_before_today = last_location["distance"] if last_location else 0

    waypoints_table = _load_waypoints_table(db, trek_id=trek_id, leg_id=leg_id)
    progress_today = steps_today * progress_utils.STRIDE
    cumulative_progress = progress_today + progress_before_today
    days_terminus, latest_waypoint, is_finished = _point_at_distance(
        waypoints_table, cumulative_progress
    )
    if is_finished:
        # make sure we do not over-shoot
        cumulative_progress = latest_waypoint["distance"]
    days_intervals = _get_days_distance_intervals(
        waypoints_table,
        from_distance=progress_before_today,
        to_distance=cumulative_progress,
    )
    address, country, photo, map_url, poi = location_apis_func(
        trek_id, leg_id, date, days_intervals, upload_func
    )

    is_new_country = (
        country is not None
        and last_location is not None
        and last_location["country"] is not None
        and country != last_location["country"]
    )

    traversal_map = mapping_func(
        db=db,
        trek_id=trek_id,
        leg_id=leg_id,
        date=date,
        last_location=last_location,
        current_location=days_terminus,
        current_distance=cumulative_progress,
        users_progress=users_progress,
        upload_func=upload_func,
    )

    factoid = (
        factoids.main(db, trek_id, leg_id, date, progress_today, cumulative_progress)
        if not is_finished
        else factoids.leg_summary(db, trek_id, leg_id)
    )
    days_achievements = achievements.main(
        db=db, trek_id=trek_id, leg_id=leg_id, date=date
    )
    days_achievements_ids = (
        [achievement["id"] for achievement in days_achievements]
        if days_achievements
        else None
    )

    location: Location = {
        "trek_id": trek_id,
        "leg_id": leg_id,
        "added_at": date,
        "latest_waypoint": latest_waypoint["id"],
        "lat": days_terminus[0],
        "lon": days_terminus[1],
        "distance": cumulative_progress,
        "address": address,
        "country": country,
        "is_new_country": is_new_country,
        "is_last_in_leg": is_finished,
        "gmap_url": map_url,
        "poi": poi,
        "photo_url": photo,
        "traversal_map_url": traversal_map,
        "achievements": days_achievements_ids,
        "factoid": factoid,
    }
    return location, days_achievements


def _save_location_data(db: Database, record: Location):
    db.append_record(Location, record)


def _save_achievements_data(db: Database, achievements: list[Achievement]):
    table = db.load_table(Achievement)
    record_table = pa.Table.from_pylist(achievements, schema=achievement_schema)
    merged_table = pa.concat_tables([table, record_table]).combine_chunks()
    db.save_table(Achievement, merged_table)


def execute_one(
    db: Database,
    trek: Trek,
    leg: Leg,
    date: pendulum.Date,
    upload_func: UploadFunc,
    outputter: t.Optional[Outputter],
) -> None:
    log.info(f"Executing update for {trek['id']} on {date}")
    trek_id = trek["id"]
    leg_id = leg["id"]
    trek_users = _users_in_trek(db, trek_id)
    trek_user_ids = [user["user_id"] for user in trek_users]
    user_records = db.load_records(User, filter=pc.field("id").isin(trek_user_ids))
    log.info(user_records)
    users_progress = _get_users_progress(
        db, trek_id, leg_id, date, user_records, trek_users
    )
    log.info(users_progress)
    _save_users_progress(db, users_progress)
    location, new_achievements = _execute_daily_progression(
        db=db,
        trek_id=trek_id,
        leg_id=leg_id,
        date=date,
        users_progress=users_progress,
        upload_func=upload_func,
        location_apis_func=location_apis.main,
        mapping_func=mapping.main,
    )
    if location is None:
        return
    _save_location_data(db, location)
    if new_achievements:
        _save_achievements_data(db, new_achievements)
    next_adder = None
    if location["is_last_in_leg"]:
        leg["is_finished"] = True
        db.upsert_record(Leg, leg, pc.field("id") == pc.scalar(leg["id"]))
        next_adder_id = get_next_leg_adder(leg["added_by"], trek_users)
        next_adder = next(user for user in user_records if user["id"] == next_adder_id)
    if outputter is not None:
        outputter.post_update(
            db, trek, users_progress, location, new_achievements, next_adder
        )


def run():
    upload_func = make_upload_f()
    with Database.get_db_mgr() as db:
        now = pendulum.now("utc")
        to_update = _get_treks_to_update(db, now)
        yesterday = now.date().subtract(days=1)
        for trek, leg in to_update:
            output_to = trek["output_to"]
            outputter = outputters[output_to] if output_to is not None else None
            if not leg["is_finished"]:
                execute_one(db, trek, leg, yesterday, upload_func, outputter)
            elif outputter is not None:
                trek_users = _users_in_trek(db, trek["id"])
                next_adder_id = get_next_leg_adder(leg["added_by"], trek_users)
                next_adder = db.load_records(
                    User, filter=pc.field("id") == pc.scalar(next_adder_id)
                )[0]
                outputter.post_leg_reminder(db, trek, next_adder)
