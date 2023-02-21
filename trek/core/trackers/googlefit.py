import typing as t  # noqa

import google.auth
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import pendulum

from trek import config
from trek.core.trackers import tracker_utils
from trek.database import Database
from trek.models import Id

scopes = [
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/userinfo.email",
]

GoogleFitToken = dict


class GooglefitUser:
    # service = GooglefitService

    def __init__(self, db: Database, user_id: Id, token: GoogleFitToken):
        self.db = db
        self.user_id = user_id
        self.credentials = _credentials_from_token(token)
        self.credentials.expiry = pendulum.from_timestamp(token["expires_at"]).naive()
        if self.credentials.expired:
            self.credentials.refresh(google.auth.transport.requests.Request())
        if not self.credentials.valid:
            raise Exception("Invalid credentials")
        self.client = build(
            "fitness", "v1", credentials=self.credentials, cache_discovery=False
        )

    def persist_token(self, token: GoogleFitToken) -> None:
        tracker_user_id = GooglefitService.tracker_user_id_from_token(token)
        tracker_utils.persist_token(
            self.db,
            token=token,
            user_id=self.user_id,
            tracker_name="googlefit",
            tracker_user_id=tracker_user_id,
        )

    def _steps_api_call(self, start_ms: int, end_ms: int) -> dict:
        return (
            self.client.users()
            .dataset()
            .aggregate(
                userId="me",
                body={
                    "aggregateBy": [
                        {
                            "dataTypeName": "com.google.step_count.delta",
                            "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps",
                        }
                    ],
                    "bucketByTime": {
                        "durationMillis": pendulum.duration(days=1).in_seconds() * 1000
                    },
                    "startTimeMillis": start_ms,
                    "endTimeMillis": end_ms,
                },
            )
            .execute()
        )

    def steps(self, date: pendulum.Date, db: Database) -> int:
        # TODO does not check tz
        start_dt = pendulum.datetime(date.year, date.month, date.day)
        start_ms = start_dt.timestamp() * 1000
        end_ms = start_dt.add(days=1).timestamp() * 1000
        data = self._steps_api_call(start_ms, end_ms)
        try:
            return data["bucket"][0]["dataset"][0]["point"][0]["value"][0]["intVal"]
        except IndexError:
            return 0

    def body(self, date: pendulum.Date):
        pass

    def user_name(self) -> str:
        user_info = _get_user_info(self.credentials)
        return user_info["email"]


class GooglefitService:
    name: t.Literal["googlefit"] = "googlefit"
    User = GooglefitUser

    def __init__(self):
        client_config = {
            "web": {
                "client_id": config.googlefit_client_id,
                "project_id": config.googlefit_project_id,
                "auth_uri": config.googlefit_auth_uri,
                "token_uri": config.googlefit_token_uri,
                "auth_provider_x509_cert_url": config.googlefit_auth_provider_x509_cert_url,
                "client_secret": config.googlefit_client_secret,
                "redirect_uris": [config.googlefit_redirect_uri],
                "javascript_origins": [config.frontend_url],
            }
        }
        flow = Flow.from_client_config(client_config, scopes=scopes)
        flow.redirect_uri = config.googlefit_redirect_uri
        self.client = flow

    def authorization_url(self) -> str:
        authorization_url, state = self.client.authorization_url(
            access_type="offline", include_granted_scopes="true"
        )
        return authorization_url

    def token(self, code: str) -> GoogleFitToken:
        self.client.fetch_token(code=code)
        credentials = self.client.credentials
        token = GoogleFitToken(
            access_token=credentials.token,
            id_token=credentials.id_token,
            refresh_token=credentials.refresh_token,
            expires_at=credentials.expiry.timestamp(),
        )
        return token

    @staticmethod
    def tracker_user_id_from_token(token: GoogleFitToken) -> Id:
        credentials = _credentials_from_token(token)
        user_info = _get_user_info(credentials)
        return Id("googlefit_" + str(user_info["id"]))


def _credentials_from_token(token):
    return Credentials(
        token=token["access_token"],
        refresh_token=token["refresh_token"],
        client_id=config.googlefit_client_id,
        client_secret=config.googlefit_client_secret,
        scopes=scopes,
        token_uri=config.googlefit_token_uri,
    )


def _get_user_info(credentials):
    user_info_service = build(
        "oauth2", "v2", credentials=credentials, cache_discovery=False
    )
    return user_info_service.userinfo().get().execute()
