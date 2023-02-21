import json
import typing as t  # noqa

import pyarrow.compute as pc

from trek.database import Database
from trek.models import Id, TrackerName, UserToken


def persist_token(
    db: Database,
    token: dict,
    user_id: Id,
    tracker_name: TrackerName,
    tracker_user_id: Id,
):
    user_token_record: UserToken = {
        "token": json.dumps(token),
        "user_id": user_id,
        "tracker_name": tracker_name,
        "tracker_user_id": tracker_user_id,
    }
    user_tracker_filter = (pc.field("user_id") == pc.scalar(user_id)) & (
        pc.field("tracker_name") == pc.scalar(tracker_name)
    )
    db.upsert_record(UserToken, user_token_record, user_tracker_filter)
    db.commit_table(UserToken)
