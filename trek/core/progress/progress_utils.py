import typing as t

import gpxpy
import pyarrow.compute as pc

from trek.database import Database
from trek.models import Id, Location, Step, TrekUser, User, Waypoint

STRIDE: t.Final = 0.75


class UserProgress(t.TypedDict):
    user: User
    trek_user: TrekUser
    step: Step


def round_meters(n: float) -> str:
    if n < 1000:
        unit = "m"
    else:
        n /= 1000
        unit = "km"
    n = round(n, 1)
    if int(n) == n:
        n = int(n)
    return f"{n} {unit}"


def point_between_waypoints(
    first_waypoint, last_waypoint, distance: float
) -> tuple[float, float]:
    angle = gpxpy.geo.get_course(
        first_waypoint["lat"],
        first_waypoint["lon"],
        last_waypoint["lat"],
        last_waypoint["lon"],
    )
    delta = gpxpy.geo.LocationDelta(distance=distance, angle=angle)
    first_waypoint_obj = gpxpy.geo.Location(
        first_waypoint["lat"], first_waypoint["lon"]
    )
    current_lat, current_lon = delta.move(first_waypoint_obj)
    return round(current_lat, 7), round(current_lon, 7)


def waypoints_between_distances(
    db: Database,
    trek_id: Id,
    leg_id: Id,
    low: float,
    high: float,
) -> list[Waypoint]:
    return (
        db.load_table(
            Waypoint,
            filter=(
                (pc.field("trek_id") == pc.scalar(trek_id))
                & (pc.field("leg_id") == pc.scalar(leg_id))
                & (pc.field("distance") >= pc.scalar(low))
                & (pc.field("distance") <= pc.scalar(high))
            ),
        )
        .sort_by("distance")
        .to_pylist()
    )


def locations_between_distances(
    db: Database,
    trek_id: Id,
    leg_id: Id,
    low: float,
    high: float,
) -> list[Location]:
    return (
        db.load_table(
            Location,
            filter=(
                (pc.field("trek_id") == pc.scalar(trek_id))
                & (pc.field("leg_id") == pc.scalar(leg_id))
                & (pc.field("distance") >= pc.scalar(low))
                & (pc.field("distance") <= pc.scalar(high))
            ),
        )
        .sort_by("added_at")
        .to_pylist()
    )
