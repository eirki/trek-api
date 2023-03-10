import pendulum
import pyarrow as pa
from ward import test

from tests.testing_utils import test_db
from trek.core.progress import achievements
from trek.database import Database, step_schema
from trek.models import Step


def _preadd_steps(db: Database, day_step_tuples, date):
    trek_id = db.make_id()
    leg_id = db.make_id()
    user_ids = [db.make_id(), db.make_id(), db.make_id()]

    step_records = []
    for day_tuple in day_step_tuples:
        for amount, user_id in zip(day_tuple, user_ids):
            step: Step = {
                "trek_id": trek_id,
                "leg_id": leg_id,
                "user_id": user_id,
                "taken_at": date,
                "amount": amount,
            }
            step_records.append(step)
        date = date.subtract(days=1)
    steps_table = pa.Table.from_pylist(step_records, schema=step_schema)
    return steps_table, trek_id, leg_id


@test("most_steps_one_day ")
def test_most_steps_one_day(db: Database = test_db):
    date = pendulum.date(2000, 2, 5)
    steps = [
        (0, 2, 0),
        (0, 0, 1),
        (0, 0, 0),
    ]
    steps_table, trek_id, leg_id = _preadd_steps(db, steps, date)
    res = achievements._most_steps_one_day(steps_table, date)
    assert res is not None
    new, old = res
    assert new == {
        "trek_id": trek_id,
        "leg_id": leg_id,
        "user_id": "00000000000000000000000000000003",
        "taken_at": pendulum.date(2000, 2, 5),
        "amount": 2,
    }
    assert old == {
        "trek_id": trek_id,
        "leg_id": leg_id,
        "user_id": "00000000000000000000000000000004",
        "taken_at": pendulum.date(2000, 2, 4),
        "amount": 1,
    }


@test("most_steps_one_day_no_record")
def test_most_steps_one_day_no_record(db: Database = test_db):
    date = pendulum.date(2000, 2, 5)
    steps = [
        (0, 1, 0),
        (0, 0, 2),
        (0, 0, 0),
    ]
    steps_table, trek_id, leg_id = _preadd_steps(db, steps, date)
    res = achievements._most_steps_one_day(steps_table, date)
    assert res is None


@test("most_steps_one_day_multiple")
def test_most_steps_one_day_multiple(db: Database = test_db):
    date = pendulum.date(2000, 2, 5)
    steps = [
        (0, 2, 2),
        (0, 0, 1),
        (0, 0, 1),
    ]
    steps_table, trek_id, leg_id = _preadd_steps(db, steps, date)
    res = achievements._most_steps_one_day(steps_table, date)
    assert res is not None
    new, old = res
    assert new == {
        "trek_id": trek_id,
        "leg_id": leg_id,
        "user_id": "00000000000000000000000000000003",
        "taken_at": pendulum.date(2000, 2, 5),
        "amount": 2,
    }
    assert old == {
        "trek_id": "00000000000000000000000000000000",
        "user_id": "00000000000000000000000000000004",
        "leg_id": "00000000000000000000000000000001",
        "taken_at": pendulum.date(2000, 2, 5),
        "amount": 2,
    }


@test("most_steps_one_week ")
def test_most_steps_one_week(db: Database = test_db):
    date = pendulum.date(2000, 2, 5)
    steps = [
        (0, 2, 0),
        (0, 0, 1),
        (0, 1, 0),
        (0, 0, 0),
        (0, 1, 0),
        (0, 0, 0),
        (0, 3, 2),
        (0, 0, 0),
        (0, 1, 0),
        (0, 0, 0),
        (0, 0, 0),
        (0, 0, 0),
    ]
    steps_table, trek_id, leg_id = _preadd_steps(db, steps, date)
    res = achievements._most_steps_one_week(steps_table, date)
    assert res is not None
    new, old = res
    assert new == {
        "amount": 7.0,
        "taken_at": pendulum.date(2000, 2, 5),
        "user_id": "00000000000000000000000000000003",
    }
    assert old == {
        "amount": 6.0,
        "taken_at": pendulum.date(2000, 2, 3),
        "user_id": "00000000000000000000000000000003",
    }


@test("most_steps_one_week_too_few_days ")
def test_most_steps_one_week_too_few_days(db: Database = test_db):
    date = pendulum.date(2000, 2, 5)
    steps = [
        (0, 2, 0),
    ]
    steps_table, trek_id, leg_id = _preadd_steps(db, steps, date)
    res = achievements._most_steps_one_week(steps_table, date)
    assert res is None


@test("most_steps_one_week_no_record")
def test_most_steps_one_week_no_record(db: Database = test_db):
    date = pendulum.date(2000, 2, 5)
    steps = [
        (0, 0, 0),
        (0, 0, 1),
        (0, 1, 0),
        (0, 0, 0),
        (0, 1, 0),
        (0, 0, 0),
        (0, 3, 2),
        (0, 0, 0),
        (0, 1, 0),
        (0, 0, 0),
        (0, 0, 0),
        (0, 0, 0),
    ]
    steps_table, trek_id, leg_id = _preadd_steps(db, steps, date)
    res = achievements._most_steps_one_week(steps_table, date)
    assert res is None


@test("longest_streak")
def test_longest_streak(db: Database = test_db):
    date = pendulum.date(2000, 2, 5)
    steps = [
        (0, 1, 0),
        (0, 3, 2),
        (1, 2, 0),
        (0, 0, 1),
        (0, 1, 2),
    ]
    steps_table, trek_id, leg_id = _preadd_steps(db, steps, date)
    res = achievements._longest_streak(steps_table, date)
    assert res is not None
    new, old = res

    assert new == {
        "amount": 3,
        "taken_at": pendulum.date(2000, 2, 5),
        "trek_id": trek_id,
        "leg_id": leg_id,
        "user_id": "00000000000000000000000000000003",
    }
    assert old == {
        "amount": 2,
        "taken_at": pendulum.date(2000, 2, 2),
        "trek_id": trek_id,
        "leg_id": leg_id,
        "user_id": "00000000000000000000000000000004",
    }


@test("longest_streak_no_record")
def test_longest_streak_no_record(db: Database = test_db):
    date = pendulum.date(2000, 2, 5)
    steps = [
        (2, 1, 0),
        (0, 3, 2),
        (1, 2, 0),
        (0, 0, 1),
        (0, 1, 2),
    ]
    steps_table, trek_id, leg_id = _preadd_steps(db, steps, date)
    res = achievements._longest_streak(steps_table, date)
    assert res is None
