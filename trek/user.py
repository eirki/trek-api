from __future__ import annotations

import base64
import json
import logging
import typing as t  # noqa
import urllib.parse
import uuid

import aiosql
from asyncpg import Connection
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from fastapi_jwt_auth import AuthJWT
import pendulum
from pydantic import BaseModel, HttpUrl

from trek import trackers
from trek.crud import queries as crud_queries
from trek.database import get_db
from trek.trackers.tracker_utils import queries as tracker_queries

log = logging.getLogger(__name__)
queries = aiosql.from_path("sql/user.sql", "psycopg")
router = APIRouter(prefix="/user", tags=["users"])


def encode_dict(data: dict) -> str:
    print("data", data)
    message = json.dumps(data)
    base64_message = base64.urlsafe_b64encode(message.encode()).decode()
    print("encode", base64_message)
    return base64_message


def decode_dict(data: str) -> dict:
    print("data", data)
    data_out = base64.urlsafe_b64decode(data.encode()).decode()
    message_out = json.loads(data_out)
    print("decode", message_out)
    return message_out


FRAGMENT_PLACEHOLDER = str(uuid.uuid4())


def add_params_to_url(url: str, params: dict) -> str:
    # urllib expects query params to come before '#'. Vue does not
    url = url.replace("#", FRAGMENT_PLACEHOLDER)
    url_parts = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(url_parts.query))
    query.update(params)
    new_url_parts = url_parts._replace(query=urllib.parse.urlencode(query))
    new_url = urllib.parse.urlunsplit(new_url_parts)
    new_url = new_url.replace(FRAGMENT_PLACEHOLDER, "#")
    return new_url


class AuthorizeResponse(BaseModel):
    auth_url: str


@router.get("/auth/{tracker_name}", response_model=AuthorizeResponse)
def authorize(tracker_name: trackers.TrackerName, redirect_url: str):
    Service = trackers.name_to_service[tracker_name]
    service = Service()
    auth_url = service.authorization_url()
    state_params = {"redirect_url": str(redirect_url)}
    encoded_params = encode_dict(state_params)
    auth_url = add_params_to_url(auth_url, params={"state": encoded_params})
    return {"auth_url": auth_url}


@router.get(
    "/add_tracker/{tracker_name}",
    response_model=AuthorizeResponse,
    operation_id="authorize",
)
def add_tracker(
    tracker_name: trackers.TrackerName,
    redirect_url: HttpUrl,
    Authorize: AuthJWT = Depends(),
):
    Authorize.jwt_required()
    user_id = Authorize.get_jwt_subject()
    Service = trackers.name_to_service[tracker_name]
    service = Service()
    auth_url = service.authorization_url()
    state_params = {"redirect_url": str(redirect_url), "user_id": user_id}
    encoded_params = encode_dict(state_params)
    auth_url = add_params_to_url(auth_url, params={"state": encoded_params})
    return {"auth_url": auth_url}


@router.get("/redirect/{tracker_name}", include_in_schema=False)
async def handle_redirect(
    tracker_name: trackers.TrackerName,
    code: str,
    state: str,
    db=Depends(get_db),
    Authorize: AuthJWT = Depends(),
):
    Service = trackers.name_to_service[tracker_name]
    service = Service()
    token = service.token(code)
    tracker_user_id = service.tracker_user_id_from_token(token)
    state_params = decode_dict(state)
    user_id_for_tracker_user_id = await tracker_queries.user_id_for_tracker_user_id(
        db, tracker_user_id=tracker_user_id
    )
    user_id_in_params = state_params.get("user_id")

    print(f"{tracker_user_id=}")
    print(f"{user_id_for_tracker_user_id=}")
    print(f"{user_id_in_params=}")

    if user_id_for_tracker_user_id is not None:
        if (
            user_id_in_params is not None
            and user_id_for_tracker_user_id != user_id_in_params
        ):
            raise Exception(
                f"Multiple user ids detected: {user_id_for_tracker_user_id=} {user_id_in_params=}"
            )
        print("new login from existing user")
        user_id = user_id_for_tracker_user_id
    elif user_id_in_params is not None:
        print("new tracker from existing user")
        user_id = user_id_in_params
    else:
        print("new user")
        user_id = await add_user(db)
    tracker_user = service.User(db=db, user_id=user_id, token=token)
    await tracker_user.persist_token(token)
    access_token = Authorize.create_access_token(subject=user_id)

    redirect_url = state_params["redirect_url"]
    redirect_url = add_params_to_url(redirect_url, {"jwt": access_token})
    print(f"{redirect_url=}")
    return RedirectResponse(redirect_url)


async def add_user(db: Connection) -> int:
    user_record = await queries.add_user(db, is_admin=False)
    user_id = user_record["user_id"]
    return user_id


class MeResponse(BaseModel):
    user_id: int
    steps_data: list
    treks_owner_of: list
    treks_user_in: list
    trackers: list


@router.get("/me", response_model=MeResponse, operation_id="authorize")
async def me(db: Connection = Depends(get_db), Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()
    user_id = Authorize.get_jwt_subject()
    token_strings = await tracker_queries.tokens_for_user(db, user_id=user_id)
    tokens = [json.loads(token_string) for token_string in token_strings]

    users = [
        trackers.name_to_service[token_data["tracker"]].User(
            user_id=token_data["user_id_"],
            token=token_data["token"],
            db=db,
        )
        for token_data in tokens
    ]
    now = pendulum.yesterday().date()
    steps_data = [user.steps(now) for user in users]
    treks_owner_of = await crud_queries.get_treks_owner_of(db, user_id=user_id)
    treks_user_in = await crud_queries.get_treks_user_in(db, user_id=user_id)
    res = {
        "user_id": user_id,
        "steps_data": steps_data,
        "treks_owner_of": treks_owner_of,
        "treks_user_in": treks_user_in,
        "trackers": [token_data["tracker"] for token_data in tokens],
    }
    return res


class IsAuthenticatedResponse(BaseModel):
    user_id: int


@router.get(
    "/is_authenticated",
    response_model=IsAuthenticatedResponse,
    operation_id="authorize",
)
async def is_authenticated(Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()
    user_id = Authorize.get_jwt_subject()
    return {"user_id": user_id}
