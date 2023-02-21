import logging
import time
import typing as t

import oauthlib
import pendulum
from withings_api import AuthScope, WithingsApi, WithingsAuth
from withings_api.common import (
    Credentials,
    GetActivityField,
    MeasureGetActivityResponse,
)

from trek import config
from trek.core.trackers import tracker_utils
from trek.database import Database
from trek.models import Id

# class WithingsToken(t.TypedDict):
#     userid: int
#     access_token: str
#     refresh_token: str
#     expires_at: float

log = logging.getLogger(__name__)

WithingsToken = dict


class WithingsUser:
    # service = WithingsService

    def __init__(self, db: Database, user_id: Id, token: WithingsToken):
        self.db = db
        self.user_id = user_id
        credentials = Credentials(
            userid=token["userid"],
            access_token=token["access_token"],
            refresh_token=token["refresh_token"],
            token_expiry=token["expires_at"],
            client_id=config.withings_client_id,
            consumer_secret=config.withings_consumer_secret,
            token_type="Bearer",
        )
        self.client: WithingsApi = WithingsApi(
            credentials, refresh_cb=self._persist_token_callback
        )

    def persist_token(self, token: WithingsToken) -> None:
        tracker_user_id = WithingsService.tracker_user_id_from_token(token)
        tracker_utils.persist_token(
            self.db,
            token=token,
            user_id=self.user_id,
            tracker_name="withings",
            tracker_user_id=tracker_user_id,
        )

    def _persist_token_callback(self, credentials: Credentials) -> None:
        log.info("withings callback")
        token = WithingsService.prepare_token(credentials)
        self.persist_token(token)
        log.info("withings callback finished")

    def _steps_api_call(self, date: pendulum.Date) -> MeasureGetActivityResponse:
        return self.client.measure_get_activity(
            data_fields=[GetActivityField.STEPS, GetActivityField.TOTAL_CALORIES],
            startdateymd=date,
            enddateymd=date.add(days=1),
        )

    def steps(self, date: pendulum.Date, db: Database) -> int:
        for _ in range(10):
            try:
                result = self._steps_api_call(date)
                break
            except oauthlib.oauth2.rfc6749.errors.CustomOAuth2Error:
                log.info("withings api call failed, retrying")
                self.client.refresh_token()
                time.sleep(4)
        else:
            log.info("withings api call failed 10 times")
            return 0
        entry = next(
            (act for act in result.activities if act.date.day == date.day),
            None,
        )
        return entry.steps if entry else 0

    def user_name(self) -> None:
        return None


class WithingsService:
    name: t.Literal["withings"] = "withings"
    User = WithingsUser

    def __init__(self):
        scope = (AuthScope.USER_ACTIVITY,)
        client = WithingsAuth(
            client_id=config.withings_client_id,
            consumer_secret=config.withings_consumer_secret,
            callback_uri=config.withings_redirect_uri,
            scope=scope,
        )
        self.client: WithingsAuth = client

    def authorization_url(self) -> str:
        url = self.client.get_authorize_url()
        return url

    def token(self, code: str) -> WithingsToken:
        credentials = self.client.get_credentials(code)
        token = self.prepare_token(credentials)
        return token

    @staticmethod
    def prepare_token(token: Credentials) -> WithingsToken:
        return WithingsToken(
            userid=token.userid,
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            expires_at=token.token_expiry,
        )

    @staticmethod
    def tracker_user_id_from_token(token: WithingsToken) -> Id:
        return Id("withings_" + str(token["userid"]))
