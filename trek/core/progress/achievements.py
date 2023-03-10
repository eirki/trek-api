import typing as t
import warnings

import pandas as pd
from pandas.errors import SettingWithCopyWarning
import pendulum
import pyarrow as pa
import pyarrow.compute as pc

from trek.database import Database
from trek.models import Achievement, Id, Step


def _check_new_achivement(
    records: list[Step], date: pendulum.Date
) -> t.Optional[tuple[Step, Step]]:
    if not records:
        return None
    if not records[0]["taken_at"] == date:
        return None
    new, old = records[0:2]
    if pd.isna(new["amount"]) or pd.isna(old["amount"]):
        return None
    return new, old


def _most_steps_one_day(
    table: pa.Table, date: pendulum.Date
) -> t.Optional[tuple[Step, Step]]:
    records = table.sort_by(
        [("amount", "descending"), ("taken_at", "ascending")]
    ).to_pylist()
    return _check_new_achivement(records, date)


def _most_steps_one_week(
    table: pa.Table, date: pendulum.Date
) -> t.Optional[tuple[Step, Step]]:
    df = (
        table.to_pandas()
        .sort_values(["user_id", "taken_at"])
        .set_index("taken_at")
        .groupby(["user_id"])["amount"]
        .rolling(7)
        .sum()
        .reset_index()
        .sort_values(["amount", "taken_at"], ascending=False)
    )
    records = df.to_dict("records")
    return _check_new_achivement(records, date)


def _longest_streak(
    table: pa.Table, date: pendulum.Date
) -> t.Optional[tuple[Step, Step]]:
    df = table.to_pandas()[["amount", "taken_at", "user_id", "trek_id", "leg_id"]]
    idx = df.groupby("taken_at")["amount"].idxmax()
    daily_max = df.iloc[idx]
    # https://joshdevlin.com/blog/calculate-streaks-in-pandas/
    start_of_streak = daily_max["user_id"] != daily_max["user_id"].shift()
    streak_ids = start_of_streak.cumsum()

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=SettingWithCopyWarning)
        daily_max["streak_length"] = streak_ids.groupby(streak_ids).cumcount() + 1
    daily_max = (
        daily_max.sort_values("streak_length", ascending=False)
        .drop(columns=["amount"])
        .rename(columns={"streak_length": "amount"})
    )
    records = daily_max.to_dict("records")
    return _check_new_achivement(records, date)


possible_achievements = [
    (
        "most_steps_one_day",
        _most_steps_one_day,
        "Flest skritt gått på en dag",
        "skritt",
    ),
    (
        "most_steps_one_week",
        _most_steps_one_week,
        "Flest skritt gått på en uke",
        "skritt",
    ),
    (
        "longest_streak",
        _longest_streak,
        "Flest førsteplasser på rad",
        "dager",
    ),
]


def main(
    db: Database, trek_id: Id, leg_id: Id, date: pendulum.Date
) -> t.Optional[list[Achievement]]:
    trek_steps = db.load_table(Step, filter=pc.field("trek_id") == pc.scalar(trek_id))
    n_days_in_trek = pc.count_distinct(trek_steps.column("taken_at")).as_py()
    if n_days_in_trek < 3:
        return None
    check_for = [(trek_steps, True)]

    leg_steps = trek_steps.filter(pc.field("leg_id") == pc.scalar(leg_id))
    n_days_in_leg = pc.count_distinct(leg_steps.column("taken_at")).as_py()
    if n_days_in_leg < 3:
        check_for.append((leg_steps, False))

    achievements: list[Achievement] = []
    for table, is_for_trek in check_for:
        for ach_type, func, description, unit in possible_achievements:
            res = func(table, date)
            if res is None:
                continue
            new, old = res
            new_achievement: Achievement = {
                "id": db.make_id(),
                "added_at": new["taken_at"],
                "amount": new["amount"],
                "user_id": new["user_id"],
                "old_added_at": old["taken_at"],
                "old_amount": old["amount"],
                "old_user_id": old["user_id"],
                "is_for_trek": is_for_trek,
                "achievement_type": ach_type,
                "description": description,
                "unit": unit,
            }
            achievements.append(new_achievement)
    return achievements
