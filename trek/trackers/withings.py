from __future__ import annotations

import asyncio
import json
import typing as t

from asyncpg import Connection
import pendulum
from withings_api import AuthScope, WithingsApi, WithingsAuth
from withings_api.common import (
    Credentials,
    GetActivityField,
    MeasureGetActivityResponse,
)

from trek import config
from trek.trackers.tracker_utils import queries

WithingsToken = dict
# class WithingsToken(t.TypedDict):
#     userid: int
#     access_token: str
#     refresh_token: str
#     expires_at: float


class WithingsUser:
    # service = WithingsService

    def __init__(
        self,
        db: Connection,
        user_id: int,
        token: WithingsToken,
    ):
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

    async def persist_token(self, token: WithingsToken) -> None:
        tracker_user_id = WithingsService.tracker_user_id_from_token(token)
        while self.db.connection()._transaction_lock.locked():
            await asyncio.sleep(1)

        async with self.db.transaction():
            await queries.persist_token(
                self.db,
                token=json.dumps(token),
                user_id_=self.user_id,
                tracker="withings",
                tracker_user_id=tracker_user_id,
            )

    def _persist_token_callback(self, credentials: Credentials) -> None:
        print("withings callback")
        token = WithingsService.prepare_token(credentials)
        asyncio.create_task(self.persist_token(token))

    def _steps_api_call(self, date: pendulum.Date) -> MeasureGetActivityResponse:
        return self.client.measure_get_activity(
            data_fields=[GetActivityField.STEPS],
            startdateymd=date,
            enddateymd=date.add(days=1),
        )

    def steps(self, date: pendulum.Date) -> t.Optional[int]:
        result = self._steps_api_call(date)
        entry = next(
            (act for act in result.activities if act.date.day == date.day),
            None,
        )
        return entry.steps if entry else 0


class WithingsService:
    name = "withings"
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
    def tracker_user_id_from_token(token: WithingsToken) -> str:
        return "withings_" + str(token["userid"])
