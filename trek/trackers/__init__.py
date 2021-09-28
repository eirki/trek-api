import typing as t

from trek.trackers.fitbit_ import FitbitService, FitbitUser
from trek.trackers.withings import WithingsService, WithingsUser

# from trek.trackers.googlefit import GooglefitService, GooglefitUser
# from trek.trackers.polar import PolarService, PolarUser

Tracker = t.Union[FitbitService, WithingsService]
TrackerUser = t.Union[FitbitUser, WithingsUser]
Token = dict
# Token = t.Union[FitbitToken, WithingsToken]
TrackerName = t.Literal["fitbit", "withings"]

name_to_service: dict[TrackerName, t.Type[Tracker]] = {
    "fitbit": FitbitService,
    # "googlefit": GooglefitService,
    # "polar": PolarService,
    "withings": WithingsService,
}
