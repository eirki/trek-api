import asyncio
import logging
from operator import itemgetter
from pathlib import Path
import typing as t

from asyncpg import Connection
import pendulum

from trek import config, database, output
from trek.progress import (
    achievements,
    activity,
    factoids,
    location_apis,
    mapping,
    progress_utils,
)
from trek.progress.progress_utils import Uploader, queries

log = logging.getLogger(__name__)


async def coordinates_for_distance(
    db: Connection, trek_id: int, leg_id: int, distance: float
) -> tuple[tuple[float, float], int, bool]:
    latest_waypoint = await queries.get_waypoint_for_distance(
        db, trek_id=trek_id, leg_id=leg_id, distance=distance
    )
    next_waypoint = await queries.get_next_waypoint_for_distance(
        db, trek_id=trek_id, leg_id=leg_id, distance=distance
    )
    if next_waypoint is None:
        finished = True
        current_lat = latest_waypoint["lat"]
        current_lon = latest_waypoint["lon"]
    else:
        finished = False
        remaining_dist = distance - latest_waypoint["distance"]
        current_lat, current_lon = progress_utils.location_between_waypoints(
            latest_waypoint, next_waypoint, remaining_dist
        )
    return (current_lat, current_lon), latest_waypoint["id"], finished


async def get_days_distance_intervals(
    db: Connection,
    trek_id: int,
    leg_id: int,
    distance_total: float,
    last_total_distance: float,
) -> t.AsyncIterator[tuple[float, float]]:
    incr_length = location_apis.poi_radius * 2
    for intermediate_distance in range(
        int(distance_total), int(last_total_distance + incr_length), -incr_length
    ):
        inter_lat_lon, *_ = await coordinates_for_distance(
            db, trek_id, leg_id, intermediate_distance
        )
        yield inter_lat_lon


async def execute_daily_progression(
    db: Connection,
    trek_id: int,
    leg_id: int,
    date: pendulum.Date,
    steps_data: list,
    user_names: list,
    uploader: Uploader,
) -> t.Optional[dict]:
    steps_data.sort(key=itemgetter("amount"), reverse=True)
    steps_today = sum(data["amount"] for data in steps_data)
    if steps_today == 0:
        return None

    last_location = await queries.most_recent_location(
        db, trek_id=trek_id, leg_id=leg_id
    )
    last_total_distance = last_location["distance"] if last_location else 0

    distance_today = steps_today * progress_utils.STRIDE
    distance_total = distance_today + last_total_distance
    days_terminus, latest_waypoint_id, finished = await coordinates_for_distance(
        db, trek_id, leg_id, distance_total
    )

    days_intervals = get_days_distance_intervals(
        db, trek_id, leg_id, distance_total, last_total_distance
    )
    address, country, photo, map_url, poi = await location_apis.main(
        trek_id, leg_id, date, days_intervals, uploader
    )

    is_new_country = (
        country != last_location["country"]
        if last_location and None not in (country, last_location["country"])
        else False
    )

    traversal_map = await mapping.main(
        db=db,
        trek_id=trek_id,
        leg_id=leg_id,
        date=date,
        last_location=last_location,
        current_location=days_terminus,
        current_distance=distance_total,
        steps_data=steps_data,
        names=user_names,
        uploader=uploader,
    )

    factoid = factoids.main(db, trek_id, leg_id, date, distance_today, distance_total)
    days_achievements = await achievements.main(db, trek_id, leg_id, date)
    progress_data = {
        "trek_id": trek_id,
        "leg_id": leg_id,
        "date": date,
        "latest_waypoint": latest_waypoint_id,
        "terminus": days_terminus,
        "distance": distance_total,
        "address": address,
        "country": country,
        "is_new_country": is_new_country,
        "map_url": map_url,
        "poi": poi,
        "photo_url": photo,
        "traversal_map_url": traversal_map,
        "days_achievements": days_achievements,  # TODO might not be able to put this as a single cell in db row
        "factoid": factoid,
    }
    return progress_data


async def commit_location_data(db: Connection, progress_data: dict):
    async with db.transaction():
        await queries.add_location(db, **progress_data)


async def execute_one(
    db: Connection, trek_id: int, leg_id: int, date: pendulum.Date, uploader: Uploader
) -> None:
    user_names = await queries.users_in_trek(db)
    steps_data = await activity.get_steps_data(db, trek_id, leg_id, user_names)
    progress_data = await execute_daily_progression(
        db, trek_id, leg_id, date, steps_data, user_names, uploader
    )
    if progress_data is None:
        return
    await commit_location_data(db, progress_data)
    await output.main.post_update(db, trek_id, leg_id, progress_data)


def make_uploader() -> Uploader:
    azure = Azure()

    async def uploader(
        data: bytes, trek_id: int, leg_id: int, date: pendulum.Date, name: str
    ) -> t.Optional[str]:
        path = (Path(name) / str(trek_id) / str(leg_id) / str(date) / name).with_suffix(
            ".jpg"
        )
        try:
            uploaded = await azure.upload(f=data, path=path.as_posix())
        except Exception:
            log.error(f"Error uploading {name} image", exc_info=True)
            return None
        url = await azure.generate_sas(uploaded.path_display)
        return url

    return uploader


async def execute_all(db, now):
    now_date = now.date()
    uploader = make_uploader()
    to_update = await queries.get_treks_to_update(db, date=now_date)
    coros = []
    for trek in to_update:
        dates_to_update = trek["last_updated_at"] - (
            now_date.subtract(days=1)
            if trek["execute_yesterdays_progress"]
            else now_date.subtract(days=2)
        )
        for date in dates_to_update:
            coros.append(execute_one(db, trek["id"], trek["leg_id"], date, uploader))
    asyncio.gather(*coros)


def run():
    db = database.get_db()
    now = pendulum.now("utc")
    asyncio.gather(execute_all(db, now))
