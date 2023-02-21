from collections import defaultdict
import logging
from operator import itemgetter
import typing as t

from accesslink import AccessLink as PolarApi
from accesslink.endpoints.daily_activity_transaction import DailyActivityTransaction
import pendulum
import pyarrow.compute as pc
from requests.exceptions import HTTPError  # type: ignore

from trek import config
from trek.core.trackers import tracker_utils
from trek.database import Database
from trek.models import Id, PolarCache

log = logging.getLogger(__name__)

PolarToken = dict


class PolarUser:
    def __init__(self, db: Database, user_id: Id, token: PolarToken):
        self.db = db
        self.user_id = user_id
        self.client = PolarApi(
            client_id=config.polar_client_id, client_secret=config.polar_client_secret
        )
        self.token = token

    def persist_token(self, token: PolarToken) -> None:
        tracker_user_id = PolarService.tracker_user_id_from_token(self.token)
        tracker_utils.persist_token(
            self.db,
            token=token,
            user_id=self.user_id,
            tracker_name="polar",
            tracker_user_id=tracker_user_id,
        )

    def _get_transaction(
        self,
    ) -> t.Optional[DailyActivityTransaction]:  # no test coverage
        trans = self.client.daily_activity.create_transaction(
            user_id=self.token["x_user_id"], access_token=self.token["access_token"]
        )
        return trans

    def steps(self, date: pendulum.Date, db: Database) -> int:
        log.info("Getting polar steps")
        trans = self._get_transaction()
        if trans is not None:
            activities = trans.list_activities()["activity-log"]
            log.info(f"number of activities: {len(activities)}")
            steps_by_date: dict[pendulum.Date, list[PolarCache]] = defaultdict(list)
            for activity in activities:
                summary = trans.get_activity_summary(activity)
                log.info(summary)
                parsed = pendulum.parse(summary["date"])
                assert isinstance(parsed, pendulum.DateTime)
                taken_at = parsed.date()

                created_at = pendulum.parse(summary["created"])
                assert isinstance(created_at, pendulum.DateTime)

                n_steps = summary["active-steps"]
                log.info(f"n steps {created_at}: {n_steps}")
                cache_entry: PolarCache = {
                    "n_steps": n_steps,
                    "created_at": created_at,
                    "user_id": self.user_id,
                    "taken_at": taken_at,
                }
                steps_by_date[taken_at].append(cache_entry)

            for activity_date, activity_list in steps_by_date.items():
                if activity_date < date:
                    # no use storing old data
                    continue
                activity_list.sort(key=itemgetter("created_at"))
                newest_entry_for_date = activity_list[-1]

                log.info(
                    f"newest_entry_for_date, {activity_date}: {newest_entry_for_date}"
                )
                db.upsert_record(
                    PolarCache,
                    newest_entry_for_date,
                    filter=(
                        (pc.field("user_id") == pc.scalar(self.user_id))
                        & (pc.field("taken_at") == pc.scalar(taken_at))
                    ),
                )
            db.commit_table(PolarCache)
            trans.commit()
        cache_records = db.load_records(
            PolarCache,
            filter=(
                (pc.field("user_id") == pc.scalar(self.user_id))
                & (pc.field("taken_at") == pc.scalar(date))
            ),
        )
        steps = (
            sum(record["n_steps"] for record in cache_records)
            if len(cache_records) > 0
            else 0
        )
        return steps

    def user_name(self) -> str:
        user_info = self.client.users.get_information(
            user_id=self.token["x_user_id"], access_token=self.token["access_token"]
        )
        return user_info["first-name"]


class PolarService:
    name: t.Literal["polar"] = "polar"
    User = PolarUser

    def __init__(self):
        client = PolarApi(
            client_id=config.polar_client_id,
            client_secret=config.polar_client_secret,
            redirect_url=config.polar_redirect_uri,
        )
        self.client: PolarApi = client

    def authorization_url(self) -> str:
        auth_url = self.client.get_authorization_url()
        return auth_url

    def token(self, code: str) -> PolarToken:
        token = self.client.get_access_token(code)
        # tracker_user_id = self.tracker_user_id_from_token(token)
        try:
            self.client.users.register(
                access_token=token["access_token"]  # , member_id=tracker_user_id
            )
        except HTTPError as e:
            log.error("register error", exc_info=True)
            # Error 409 Conflict means that the user has already been registered for this client.
            if e.response.status_code != 409:
                raise e
        return token

    @staticmethod
    def tracker_user_id_from_token(token: PolarToken) -> Id:
        return Id("polar___" + str(token["x_user_id"]))
