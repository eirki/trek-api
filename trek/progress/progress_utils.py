import typing as t

import aiosql
import gpxpy
import pendulum

STRIDE: t.Final = 0.75
queries = aiosql.from_path("sql/progress.sql", "psycopg")


def location_between_waypoints(
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
    return current_lat, current_lon


class Uploader(t.Protocol):
    async def __call__(
        self, data: bytes, trek_id: int, leg_id: int, date: pendulum.Date, name: str
    ) -> t.Optional[str]:
        ...


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
