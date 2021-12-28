from __future__ import annotations

import asyncio
import logging
import typing as t

from databases import Database
import fitbit
from fitbit import Fitbit as FitbitApi
from fitbit.api import FitbitOauth2Client
import pendulum

from trek import config
from trek.trackers._tracker_utils import queries

log = logging.getLogger(__name__)

FitbitToken = dict
# class FitbitToken(t.TypedDict):
#     user_id: str
#     access_token: str
#     refresh_token: str
#     expires_at: float


class FitbitUser:
    # service = FitbitService

    def __init__(
        self,
        db: Database,
        user_id: int,
        token: FitbitToken,
    ):
        self.db = db
        self.user_id = user_id
        self.client = FitbitApi(
            config.fitbit_client_id,
            config.fitbit_client_secret,
            access_token=token["access_token"],
            refresh_token=token["refresh_token"],
            expires_at=token["expires_at"],
            refresh_cb=self._persist_token_callback,
            system=FitbitApi.METRIC,
        )

    async def persist_token(self, token: FitbitToken) -> None:
        tracker_user_id = FitbitService.tracker_user_id_from_token(token)
        while self.db.connection()._transaction_lock.locked():
            await asyncio.sleep(1)
        async with self.db.transaction():
            await queries.persist_token(
                self.db,
                token=token,
                user_id_=self.user_id,
                tracker="fitbit",
                tracker_user_id=tracker_user_id,
            )

    def _persist_token_callback(self, token: FitbitToken) -> None:
        print("fitbit callback")
        token = FitbitService.prepare_token(token)
        coro = self.persist_token(token)
        asyncio.create_task(coro)
        print("fitbit callback finished")

    def _steps_api_call(self, date: pendulum.Date) -> dict:
        kwargs = {"resource": "activities/steps", "base_date": date, "period": "1d"}
        exc = None
        data = None
        for _ in range(10):
            try:
                data = self.client.time_series(**kwargs)
                break
            except fitbit.exceptions.HTTPServerError as e:
                log.info("Error fetching fitbit data. Retrying")
                exc = e
        if data is None:
            assert exc is not None
            raise exc
        return data

    def steps(self, date: pendulum.Date) -> t.Optional[int]:
        data = self._steps_api_call(date)
        if not data["activities-steps"]:
            return 0
        entry = data["activities-steps"][0]
        return int(entry["value"]) if entry else 0


class FitbitService:
    name = "fitbit"
    User = FitbitUser

    def __init__(self):
        client = FitbitOauth2Client(
            config.fitbit_client_id,
            config.fitbit_client_secret,
            redirect_uri=config.fitbit_redirect_uri,
            timeout=10,
        )
        self.client: FitbitOauth2Client = client

    def authorization_url(self) -> str:
        scope = ["activity"]
        url, _ = self.client.authorize_token_url(scope=scope)
        return url

    def token(self, code: str) -> FitbitToken:
        self.client.fetch_access_token(code)
        token = self.prepare_token(self.client.session.token)
        return token

    @staticmethod
    def prepare_token(token) -> FitbitToken:
        return dict(token)

    @staticmethod
    def tracker_user_id_from_token(token: FitbitToken) -> str:
        return "fitbit_" + str(token["user_id"])
