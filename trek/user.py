from __future__ import annotations

import logging

import aiosql
from databases import Database
from fastapi import APIRouter, Depends
from fastapi_jwt_auth import AuthJWT
import pendulum
from pydantic import BaseModel

from trek import trackers
from trek.database import DatabasesAdapter, get_db

log = logging.getLogger(__name__)
queries = aiosql.from_path("sql/user.sql", DatabasesAdapter)
router = APIRouter(prefix="/user", tags=["users"])


class AuthorizeResponse(BaseModel):
    auth_url: str


@router.get(
    "/auth/{tracker_name}",
    response_model=AuthorizeResponse,
)
def authorize(tracker_name: trackers.TrackerName):
    service = trackers.init_service(tracker_name)
    auth_url = service.authorization_url()
    return {"auth_url": auth_url}


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: int


@router.get("/redirect/{tracker_name}", response_model=Token)
async def handle_redirect(
    tracker_name: trackers.TrackerName,
    code: str,
    db=Depends(get_db),
    Authorize: AuthJWT = Depends(),
):
    service = trackers.init_service(tracker_name)
    tracker_user_id, token = service.token(code)
    user_id = await queries.user_id_for_tracker_user_id(
        db, tracker_user_id=tracker_user_id
    )
    if user_id is None:
        user_id = await add_user(db, tracker_user_id)
    await service.persist_token(db, user_id=user_id, token=token)
    trackers.init_user(db=db, tracker_name=tracker_name, user_id=user_id, token=token)
    access_token = Authorize.create_access_token(subject=user_id)
    return {"access_token": access_token, "token_type": "bearer"}


async def add_user(db: Database, tracker_user_id: str) -> int:
    user_record = await queries.add_user(db, tracker_user_id=tracker_user_id)
    user_id = user_record["user_id"]
    return user_id


@router.get("/me", operation_id="authorize")
async def me(db: Database = Depends(get_db), Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()
    user_id = Authorize.get_jwt_subject()
    async with db.transaction():
        tokens = await db.fetch_all(
            "select * from user_token where user_id_ = :user_id", {"user_id": user_id}
        )
    users = [
        trackers.init_user(
            user_id=token_data["user_id_"],
            token=token_data["token"],
            tracker_name=token_data["tracker"],
            db=db,
        )
        for token_data in tokens
    ]
    now = pendulum.yesterday().date()
    data = [(user.user_id, user.steps(now)) for user in users]
    return data


# @router.get("/{user_id}")
# async def get_user(user_id: int, db: Database = Depends(get_db)):
#     user_record = await queries.get_user(db, id=user_id)
#     return dict(user_record)


# @router.get("/")
# async def get_all_user(db: Database = Depends(get_db)):
#     users = await queries.get_all_users(db)
#     all_users = [dict(user) for user in users]
#     return all_users
