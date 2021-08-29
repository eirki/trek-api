from __future__ import annotations

import logging

import aiosql
from databases import Database
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from trek.database import DatabasesAdapter, get_db

log = logging.getLogger(__name__)
queries = aiosql.from_path("sql/user.sql", DatabasesAdapter)
router = APIRouter(prefix="/user", tags=["users"])


class AddRequest(BaseModel):
    name: str


@router.post("/")
async def add_user(request: AddRequest, db: Database = Depends(get_db)):
    user_record = await queries.add_user(db, name=request.name)
    user_id = user_record["user_id"]
    return {"user_id": user_id}


@router.get("/{user_id}")
async def get_user(user_id: int, db: Database = Depends(get_db)):
    user_record = await queries.get_user(db, id=user_id)
    return dict(user_record)


@router.get("/")
async def get_all_user(db: Database = Depends(get_db)):
    users = await queries.get_all_users(db)
    all_users = [dict(user) for user in users]
    return all_users
