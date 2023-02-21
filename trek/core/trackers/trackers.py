import typing as t

from trek.core.trackers.fitbit_ import FitbitService, FitbitUser
from trek.core.trackers.googlefit import GooglefitService, GooglefitUser
from trek.core.trackers.polar import PolarService, PolarUser
from trek.core.trackers.withings import WithingsService, WithingsUser
from trek.models import TrackerName

Tracker = t.Union[FitbitService, WithingsService, GooglefitService, PolarService]
TrackerUser = t.Union[FitbitUser, WithingsUser, GooglefitUser, PolarUser]
Token = dict
# Token = t.Union[FitbitToken, WithingsToken]

name_to_service: dict[TrackerName, t.Type[Tracker]] = {
    "fitbit": FitbitService,
    "googlefit": GooglefitService,
    "polar": PolarService,
    "withings": WithingsService,
}
