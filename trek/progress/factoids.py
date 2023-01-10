import math

from asyncpg import Connection
import pendulum

from trek.progress.progress_utils import round_meters


def remaining_distance_leg(
    db: Connection,
    trek_id: int,
    leg_id: int,
    distance_total: float,
    **kwargs,
) -> str:
    distance_remaining = trek_data["distance"] - distance_total
    return (
        f"Nå har vi gått {round_meters(distance_leg)} på denne etappen - "
        f"vi har igjen {round_meters(distance_remaining)}."
    )


def eta_average_leg(
    db: Connection, trek_id: int, leg_id: int, date: pendulum.Date, **kwargs
):
    n_days = (date - trek_data["started_at"]).days + 1
    distance_average = distance_total / n_days
    distance_remaining = trek_data["distance"] - distance_total
    days_remaining = math.ceil(distance_remaining / distance_average)
    eta = date.add(days=days_remaining)
    return (
        f"Vi har gått i snitt {round_meters(distance_average_leg)} hver dag denne etappen. "
        f"Holder vi dette tempoet er vi fremme den {eta.format('DD. MMMM YYYY', locale='nb')}, "
        f"om {days_remaining} dager."
    )


def average_trek(
    db: Connection, trek_id: int, leg_id: int, date: pendulum.Date, **kwargs
):
    return (
        f"Nå har vi gått {round_meters(distance_total)} totalt på reisen,"
        f"Gjennomsnittet er {round_meters(distance_average_trek)} hver dag. "
    )


def weekly_summary(
    db: Connection, trek_id: int, leg_id: int, date: pendulum.Date, **kwargs
):
    steps_week = sum(datum["amount"] for datum in data)
    distance_week = steps_week * common.STRIDE
    max_week = sorted(data, key=itemgetter("amount"))[-1]
    max_week_distance = round_meters(max_week["amount"] * common.STRIDE)
    return (
        f"Denne uken har vi gått {round_meters(distance_week)} til sammen. "
        f"Garglingen som gikk lengst var {max_week['first_name']}, med {max_week_distance}!"
    )


def main(
    db: Connection,
    trek_id: int,
    leg_id: int,
    date: pendulum.Date,
    distance_today: float,
    distance_total: float,
) -> str:

    switch = {
        pendulum.SUNDAY: remaining_distance_leg,
        pendulum.MONDAY: eta_average_leg,
        pendulum.TUESDAY: average_trek,
        pendulum.WEDNESDAY: remaining_distance_leg,
        pendulum.THURSDAY: eta_average_leg,
        pendulum.FRIDAY: average_trek,
        pendulum.SATURDAY: weekly_summary,
    }
    func = switch[date.day_of_week]

    result = func(
        db=db,
        trek_id=trek_id,
        leg_id=leg_id,
        date=date,
        distance_today=distance_today,
        distance_total=distance_total,
    )
    return result
