import math
from operator import itemgetter
import typing as t  # noqa

import pendulum
import pyarrow.compute as pc

from trek.core.progress.progress_utils import STRIDE, round_meters
from trek.database import Database
from trek.models import Id, Location, Step, User, Waypoint


def _get_leg_total_distance(
    db: Database,
    trek_id: Id,
    leg_id: Id,
) -> float:
    waypoints_table = db.load_table(
        Waypoint,
        filter=(
            (pc.field("trek_id") == pc.scalar(trek_id))
            & (pc.field("leg_id") == pc.scalar(leg_id))
        ),
        columns=["distance"],
    )
    scalar = pc.max(waypoints_table.column("distance"))
    value = scalar.as_py()
    return value


def remaining_distance_leg(
    db: Database,
    trek_id: Id,
    leg_id: Id,
    cumulative_progress: float,
    **kwargs,
) -> str:
    leg_total_distance = _get_leg_total_distance(db, trek_id, leg_id)
    distance_remaining = max(leg_total_distance - cumulative_progress, 0)
    return (
        f"Nå har vi gått {round_meters(cumulative_progress)} på denne etappen - "
        f"vi har igjen {round_meters(distance_remaining)}."
    )


def eta_average_leg(
    db,
    trek_id: Id,
    leg_id: Id,
    date: pendulum.Date,
    cumulative_progress: float,
    **kwargs,
) -> str:
    locations_table = db.load_table(
        Location,
        filter=(
            (pc.field("trek_id") == pc.scalar(trek_id))
            & (pc.field("leg_id") == pc.scalar(leg_id))
        ),
    )
    n_days = locations_table.num_rows + 1
    distance_average = cumulative_progress / n_days

    leg_total_distance = _get_leg_total_distance(db, trek_id, leg_id)
    distance_remaining = leg_total_distance - cumulative_progress

    days_remaining = math.ceil(distance_remaining / distance_average)
    eta = date.add(days=days_remaining)
    return (
        f"Vi har gått i snitt {round_meters(distance_average)} hver dag denne etappen. "
        f"Holder vi dette tempoet er vi fremme den {eta.format('DD. MMMM YYYY', locale='nb')}, "
        f"om {days_remaining} dager."
    )


# def average_trek(db, trek_id: Id, leg_id: Id, date: pendulum.Date, **kwargs) -> str:
#     return (
#         f"Nå har vi gått {round_meters(cumulative_progress)} totalt på reisen,"
#         f"Gjennomsnittet er {round_meters(distance_average_trek)} hver dag. "
#     )


def weekly_summary(
    db, trek_id: Id, leg_id: Id, date: pendulum.Date, **kwargs
) -> t.Optional[str]:
    one_week_ago = date.subtract(weeks=1)
    users_sum_steps = (
        db.load_table(
            Step,
            filter=(
                (pc.field("trek_id") == pc.scalar(trek_id))
                & (pc.field("leg_id") == pc.scalar(leg_id))
                & (pc.field("taken_at") > pc.scalar(one_week_ago))
            ),
        )
        .group_by("user_id")
        .aggregate([("amount", "sum")])
    ).to_pylist()
    if len(users_sum_steps) == 0:
        return None
    top_user = sorted(users_sum_steps, key=itemgetter("amount_sum"))[-1]
    user_data = db.load_table(
        User, filter=pc.field("id") == top_user["user_id"]
    ).to_pylist()[0]
    max_week_distance = round_meters(top_user["amount_sum"] * STRIDE)

    together_week_steps = sum(user["amount_sum"] for user in users_sum_steps)
    together_week_distance = together_week_steps * STRIDE
    return (
        f"Denne uken har vi gått {round_meters(together_week_distance)} til sammen. "
        f"Den som gikk lengst var {user_data['name']}, med {max_week_distance}!"
    )


def leg_summary(db, trek_id: Id, leg_id: Id) -> str:
    location_table = db.load_table(
        Location,
        filter=(
            (pc.field("trek_id") == pc.scalar(trek_id))
            & (pc.field("leg_id") == pc.scalar(leg_id))
        ),
        columns=["added_at"],
    )
    n_days = location_table.num_rows

    users_sum_steps = (
        db.load_table(
            Step,
            filter=(
                (pc.field("trek_id") == pc.scalar(trek_id))
                & (pc.field("leg_id") == pc.scalar(leg_id))
            ),
        )
        .group_by("user_id")
        .aggregate([("amount", "sum")])
    ).to_pylist()
    top_user = sorted(users_sum_steps, key=itemgetter("amount_sum"))[-1]
    user_data = db.load_table(
        User, filter=pc.field("id") == top_user["user_id"]
    ).to_pylist()[0]
    max_total_distance = round_meters(top_user["amount_sum"] * STRIDE)

    return (
        f"Denne etappen tok oss {n_days} dager. "
        f"Den som gikk lengst var {user_data['name']}, med {max_total_distance}!"
    )


def main(
    db: Database,
    trek_id: Id,
    leg_id: Id,
    date: pendulum.Date,
    progress_today: float,
    cumulative_progress: float,
) -> t.Optional[str]:

    switch = {
        pendulum.SUNDAY: remaining_distance_leg,
        pendulum.MONDAY: eta_average_leg,
        pendulum.TUESDAY: remaining_distance_leg,
        pendulum.WEDNESDAY: eta_average_leg,
        pendulum.THURSDAY: remaining_distance_leg,
        pendulum.FRIDAY: eta_average_leg,
        pendulum.SATURDAY: weekly_summary,
    }
    func = switch[date.day_of_week]

    result = func(  # type: ignore
        db=db,
        trek_id=trek_id,
        leg_id=leg_id,
        date=date,
        progress_today=progress_today,
        cumulative_progress=cumulative_progress,
    )
    return result
