from itertools import cycle
import typing as t  # noqa

from fastapi import HTTPException
import pyarrow.compute as pc

from trek.database import Database
from trek.models import Id, Trek, TrekUser
from trek.utils import pairwise


def get_next_leg_adder(most_recent_adder_id: Id, trek_users: list[TrekUser]) -> Id:
    # used in crud and progress.progress
    trek_user_ids = [user["user_id"] for user in trek_users]
    assert most_recent_adder_id in trek_user_ids
    next_adder_id = next(
        user_id
        for prev_user_id, user_id in pairwise(cycle(trek_user_ids))
        if prev_user_id == most_recent_adder_id
    )
    return next_adder_id


def assert_trek_owner(db: Database, trek_id: Id, user_id: Id) -> None:
    trek_table = db.load_table(Trek, filter=pc.field("id") == pc.scalar(trek_id))
    assert trek_table.num_rows == 1
    owner_id = trek_table.column("owner_id").to_pylist()[0]
    if not owner_id == user_id:
        raise HTTPException(status_code=403, detail="Forbidden")


def assert_trek_exists(db: Database, trek_id: Id) -> None:
    trek_table = db.load_table(Trek, filter=pc.field("id") == pc.scalar(trek_id))
    if not trek_table.num_rows > 0:
        raise HTTPException(status_code=403, detail="Trek not found")


def assert_trek_participant(db: Database, trek_id: Id, user_id: Id) -> None:
    if not is_trek_participant(db, trek_id, user_id):
        raise HTTPException(status_code=403, detail="Forbidden")


def is_trek_participant(db: Database, trek_id: Id, user_id: Id) -> bool:
    trek_user_table = db.load_table(
        TrekUser,
        filter=(
            (pc.field("trek_id") == pc.scalar(trek_id))
            & (pc.field("user_id") == pc.scalar(user_id))
        ),
    )
    return trek_user_table.num_rows > 0
