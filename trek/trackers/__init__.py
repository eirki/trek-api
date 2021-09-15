import typing as t

from databases import Database

from trek.trackers.fitbit_ import FitbitService, FitbitUser
from trek.trackers.withings import WithingsService, WithingsUser

# from trek.trackers.googlefit import GooglefitService, GooglefitUser
# from trek.trackers.polar import PolarService, PolarUser

Tracker = t.Union[FitbitService, WithingsService]
TrackerUser = t.Union[FitbitUser, WithingsUser]
Token = dict
# Token = t.Union[FitbitToken, WithingsToken]
TrackerName = t.Literal["fitbit", "withings"]


def init_service(tracker_name: TrackerName) -> Tracker:
    trackers: dict[TrackerName, t.Type[Tracker]] = {
        "fitbit": FitbitService,
        # "googlefit": GooglefitService,
        # "polar": PolarService,
        "withings": WithingsService,
    }
    service = trackers[tracker_name]()
    return service


def init_user(
    db: Database,
    tracker_name: TrackerName,
    user_id: int,
    token: Token,
) -> TrackerUser:
    trackers: dict[TrackerName, t.Type[TrackerUser]] = {
        "fitbit": FitbitUser,
        # "googlefit": GooglefitUser,
        # "polar": PolarUser,
        "withings": WithingsUser,
    }
    User = trackers[tracker_name]
    user = User(
        db=db,
        user_id=user_id,
        token=token,
    )
    return user
