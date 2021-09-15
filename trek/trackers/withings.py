from __future__ import annotations

import asyncio
from functools import partial
import typing as t

from databases import Database
import pendulum
from withings_api import AuthScope, WithingsApi, WithingsAuth
from withings_api.common import (
    Credentials,
    GetActivityField,
    MeasureGetActivityResponse,
)

from trek import config
from trek.trackers._tracker_utils import queries

WithingsToken = dict
# class WithingsToken(t.TypedDict):
#     userid: int
#     access_token: str
#     refresh_token: str
#     expires_at: float


class WithingsService:
    name = "withings"

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

    def token(self, code: str) -> tuple[str, WithingsToken]:
        credentials = self.client.get_credentials(code)
        token = WithingsToken(
            userid=credentials.userid,
            access_token=credentials.access_token,
            refresh_token=credentials.refresh_token,
            expires_at=credentials.token_expiry,
        )
        return str(credentials.userid), token

    @staticmethod
    async def persist_token(db: Database, user_id: int, token: WithingsToken) -> None:
        async with db.transaction():
            await queries.persist_token(
                db,
                token=token,
                user_id_=user_id,
                tracker="withings",
            )

    @classmethod
    def _sync_persist_credentials(
        cls, db: Database, user_id: int, credentials: Credentials
    ) -> None:
        token = WithingsToken(
            userid=credentials.userid,
            access_token=credentials.access_token,
            refresh_token=credentials.refresh_token,
            expires_at=credentials.token_expiry,
        )
        asyncio.run(cls.persist_token(db, user_id, token))


class WithingsUser:
    service = WithingsService

    def __init__(
        self,
        db: Database,
        user_id: int,
        token: WithingsToken,
    ):
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
            credentials,
            refresh_cb=partial(
                self.service._sync_persist_credentials, db=db, user_id=user_id
            ),
        )

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
