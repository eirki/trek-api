import json
import logging
import typing as t  # noqa

from fastapi_jwt_auth import AuthJWT
import pendulum
import pyarrow as pa
import pyarrow.compute as pc
from pydantic import BaseModel

from trek import exceptions as exc
from trek import utils
from trek.core.trackers import trackers
from trek.core.trackers.trackers import Tracker
from trek.database import Database, user_schema
from trek.models import Id, TrackerName, Trek, TrekUser, User, UserToken

log = logging.getLogger(__name__)


def _user_id_for_tracker_user_id(db: Database, tracker_user_id: Id) -> t.Optional[Id]:
    table = db.load_table(
        UserToken,
        filter=pc.field("tracker_user_id") == pc.scalar(tracker_user_id),
    )
    if table.num_rows == 0:
        return None
    return table.column("user_id").to_pylist()[0]


def _tokens_for_user(db: Database, user_id: Id) -> list[UserToken]:
    user_tokens = db.load_records(
        UserToken, filter=pc.field("user_id") == pc.scalar(user_id)
    )
    return user_tokens


def _get_treks_owner_of(db: Database, user_id: Id) -> list[Id]:
    return (
        db.load_table(Trek, filter=pc.field("owner_id") == pc.scalar(user_id))
        .column("id")
        .to_pylist()
    )


def _get_treks_user_in(db: Database, user_id: Id) -> list[Id]:
    return (
        db.load_table(TrekUser, filter=pc.field("user_id") == pc.scalar(user_id))
        .column("trek_id")
        .to_pylist()
    )


def _add_user(
    db: Database, user_id: Id, tracker_name: TrackerName, user_name: t.Optional[str]
) -> None:
    user_record: User = {
        "id": user_id,
        "is_admin": False,
        "active_tracker": tracker_name,
        "name": user_name,
    }
    db.append_record(User, user_record)


def _set_user_active_tracker(
    db: Database, user_id: Id, tracker_name: TrackerName
) -> None:
    user_records = db.load_records(User)
    user_record = next(rec for rec in user_records if rec["id"] == user_id)
    user_record["active_tracker"] = tracker_name
    users_table = pa.Table.from_pylist(user_records, schema=user_schema)
    db.save_table(User, users_table)


class AuthorizeResponse(BaseModel):
    auth_url: str


def authorize(service: Tracker, frontend_redirect_url: str) -> AuthorizeResponse:
    auth_url = service.authorization_url()
    state_params = {"frontend_redirect_url": str(frontend_redirect_url)}
    encoded_params = utils.encode_dict(state_params)
    auth_url = utils.add_params_to_url(auth_url, params={"state": encoded_params})
    return AuthorizeResponse(auth_url=auth_url)


def add_tracker(
    service: Tracker, frontend_redirect_url: str, user_id: Id
) -> AuthorizeResponse:
    auth_url = service.authorization_url()
    state_params = {
        "frontend_redirect_url": str(frontend_redirect_url),
        "user_id": user_id,
    }
    encoded_params = utils.encode_dict(state_params)
    auth_url = utils.add_params_to_url(auth_url, params={"state": encoded_params})
    return AuthorizeResponse(auth_url=auth_url)


def handle_redirect(
    service: Tracker, code: str, state: str, db: Database, Authorize: AuthJWT
) -> str:
    token = service.token(code)
    tracker_user_id = service.tracker_user_id_from_token(token)
    state_params = utils.decode_dict(state)
    user_id_for_tracker_user_id = _user_id_for_tracker_user_id(
        db, tracker_user_id=tracker_user_id
    )
    user_id_in_params = state_params.get("user_id")

    log.info(f"{tracker_user_id=}")
    log.info(f"{user_id_for_tracker_user_id=}")
    log.info(f"{user_id_in_params=}")

    if user_id_for_tracker_user_id is not None:
        if (
            user_id_in_params is not None
            and user_id_for_tracker_user_id != user_id_in_params
        ):
            raise Exception(
                f"Multiple user ids detected: {user_id_for_tracker_user_id=} {user_id_in_params=}"
            )
        log.info("new login from existing user")
        user_id = user_id_for_tracker_user_id
        tracker_user = service.User(db=db, user_id=user_id, token=token)
    elif user_id_in_params is not None:
        log.info("new tracker from existing user")
        user_id = user_id_in_params
        tracker_user = service.User(db=db, user_id=user_id, token=token)
        _set_user_active_tracker(db, user_id, service.name)
    else:
        log.info("new user")
        user_id = db.make_id()
        tracker_user = service.User(db=db, user_id=user_id, token=token)
        user_name = tracker_user.user_name()
        _add_user(db, user_id=user_id, tracker_name=service.name, user_name=user_name)

    tracker_user.persist_token(
        token
    )  # TODO why is token repeated here, tracker_user has token in state?
    access_token = Authorize.create_access_token(subject=user_id)

    frontend_redirect_url = state_params["frontend_redirect_url"]
    frontend_redirect_url = utils.add_params_to_url(
        frontend_redirect_url, {"jwt": access_token}
    )
    log.info(f"{frontend_redirect_url=}")
    return frontend_redirect_url


class MeResponse(BaseModel):
    user_id: Id
    name: t.Optional[str]
    is_admin: bool
    steps_data: list
    treks_owner_of: list[Id]
    treks_user_in: list[Id]
    all_trackers: list[TrackerName]
    active_tracker: TrackerName


def me(db: Database, user_id: Id) -> MeResponse:
    user_records = db.load_records(User, filter=pc.field("id") == pc.scalar(user_id))
    if not user_records:
        raise exc.ServerException(
            exc.E101Error(status_code=1, detail="user_id not found")
        )
    user_record = user_records[0]
    token_records = _tokens_for_user(db, user_id=user_id)
    steps_data = []
    now = pendulum.yesterday().date()
    for token_data in token_records:
        try:
            tracker_user = trackers.name_to_service[token_data["tracker_name"]].User(
                user_id=token_data["user_id"],
                token=json.loads(token_data["token"]),
                db=db,
            )
            steps = tracker_user.steps(now, db)
        except Exception as e:
            log.info(f"Failed to authenticate tracker user: {e}", exc_info=True)
        else:
            steps_data.append(steps)
    treks_owner_of = _get_treks_owner_of(db, user_id=user_id)
    treks_user_in = _get_treks_user_in(db, user_id=user_id)
    res = MeResponse(
        user_id=user_id,
        name=user_record["name"],
        is_admin=user_record["is_admin"],
        steps_data=steps_data,
        treks_owner_of=treks_owner_of,
        treks_user_in=treks_user_in,
        all_trackers=[token_data["tracker_name"] for token_data in token_records],
        active_tracker=user_record["active_tracker"],
    )
    return res


class IsAuthenticatedResponse(BaseModel):
    user_id: Id


def is_authenticated(db: Database, user_id: Id) -> IsAuthenticatedResponse:
    user_records = db.load_records(User, filter=pc.field("id") == pc.scalar(user_id))
    if not user_records:
        raise exc.ServerException(
            exc.E101Error(status_code=1, detail="user_id not found")
        )
    return IsAuthenticatedResponse(user_id=user_id)


class EditUserRequest(BaseModel):
    name: t.Optional[str] = None
    active_tracker: t.Optional[TrackerName] = None


def edit_user(request: EditUserRequest, db: Database, user_id: Id):
    user_filter = pc.field("id") == pc.scalar(user_id)
    user_table = db.load_table(User)
    try:
        user_record = user_table.filter(user_filter).to_pylist()[0]
    except IndexError:
        raise exc.ServerException(
            exc.E101Error(status_code=1, detail="user_id not found")
        )
    new_user_data = request.dict(exclude_none=True, exclude_unset=True)
    user_record.update(**new_user_data)

    record_table = pa.Table.from_pylist([user_record], schema=user_schema)
    other_users_table = user_table.filter(~user_filter)
    merged_table = pa.concat_tables([other_users_table, record_table])
    db.save_table(User, merged_table)
