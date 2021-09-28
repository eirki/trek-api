from __future__ import annotations

import logging

import aiosql
from databases import Database
from fastapi import APIRouter, Depends, HTTPException
from fastapi_jwt_auth import AuthJWT
from geopy.distance import distance
import pendulum
from pydantic import BaseModel, Field

from trek.database import DatabasesAdapter, get_db
from trek.utils import protect_endpoint

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/trek", tags=["treks"], dependencies=[Depends(protect_endpoint)]
)
queries = aiosql.from_path("sql/crud.sql", DatabasesAdapter)


async def assert_trek_owner(db: Database, trek_id: int, user_id: int) -> None:
    if not await queries.is_trek_owner(db, trek_id=trek_id, user_id=user_id):
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/{trek_id}/invite/")
async def add_user_to_trek(
    trek_id: int,
    db: Database = Depends(get_db),
    Authorize: AuthJWT = Depends(),
):
    user_id = Authorize.get_jwt_subject()
    await assert_trek_owner(db, trek_id, user_id)
    # trek_data = await queries.get_trek(db, trek_id=trek_id)
    # record = GetResponse(**trek_data)
    # return record


class AddRequest(BaseModel):
    origin: str
    users: list[int]


@router.post("/")
async def add_trek(
    request: AddRequest,
    db: Database = Depends(get_db),
    Authorize: AuthJWT = Depends(),
):
    user_id = Authorize.get_jwt_subject()
    trek_record = await queries.add_trek(db, origin=request.origin, owner_id=user_id)
    trek_id = trek_record["id"]
    users_in = [{"trek_id": trek_id, "user_id": user_id} for user_id in request.users]
    await queries.add_trek_users(db, users_in)
    return {"trek_id": trek_id}


class GetResponse(BaseModel):
    id: int
    origin: str
    users: list[int]
    leg_id: int
    leg_destination: str
    leg_added_at: pendulum.DateTime


@router.get("/{trek_id}", response_model=GetResponse)
async def get_trek(
    trek_id: int,
    db: Database = Depends(get_db),
    Authorize: AuthJWT = Depends(),
):
    user_id = Authorize.get_jwt_subject()
    await assert_trek_owner(db, trek_id, user_id)
    trek_data = await queries.get_trek(db, trek_id=trek_id)
    record = GetResponse(**trek_data)
    return record


@router.get("/}", response_model=GetResponse)
async def get_all_treks(
    db: Database = Depends(get_db),
    Authorize: AuthJWT = Depends(),
):
    user_id = Authorize.get_jwt_subject()
    trek_data = await queries.get_all_treks(db, user_id=user_id)
    record = GetResponse(**trek_data)
    return record


class AddLegRequest(BaseModel):
    destination: str
    waypoints: list = Field(
        ...,
        description="List of tuples containing 3 floats: lat, lon and elevation",
        example=[
            [10.671114, 59.332889, 18.35],
            [10.671664, 59.333243, 18.31],
            [10.671857, 59.333329, 18.32],
            [10.672099, 59.333292, 17.51],
        ],
    )


@router.post("/{trek_id}")
async def add_leg(
    trek_id: int,
    request: AddLegRequest,
    db: Database = Depends(get_db),
    Authorize: AuthJWT = Depends(),
):
    user_id = Authorize.get_jwt_subject()
    await assert_trek_owner(db, trek_id, user_id)
    leg_record = await queries.add_leg(
        db,
        trek_id=trek_id,
        destination=request.destination,
        added_at=pendulum.now("utc"),
    )
    leg_id = leg_record["id"]
    waypoints_in = waypoint_tuple_to_dicts(trek_id, leg_id, request.waypoints)
    await queries.add_waypoints(db, waypoints_in)


def waypoint_tuple_to_dicts(
    trek_id: int, leg_id: int, waypoints: list[tuple[float, float, float]]
) -> list[dict]:
    result = []
    lat, lon, elevation = waypoints[0]
    first_waypoint = {
        "trek_id": trek_id,
        "leg_id": leg_id,
        "lat": lat,
        "lon": lon,
        "elevation": elevation,
        "distance": 0,
    }
    result.append(first_waypoint)
    prev_waypoint = first_waypoint
    for lat, lon, elevation in waypoints[1:]:
        distance_from_prev = distance(
            (prev_waypoint["lat"], prev_waypoint["lon"]),
            (lat, lon),
        ).m
        cumulative_distance = prev_waypoint["distance"] + distance_from_prev
        waypoint = {
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": lat,
            "lon": lon,
            "elevation": elevation,
            "distance": cumulative_distance,
        }
        result.append(waypoint)
        prev_waypoint = waypoint
    return result


@router.delete("/{trek_id}")
async def delete_trek(
    trek_id: int,
    db: Database = Depends(get_db),
    Authorize: AuthJWT = Depends(),
):
    user_id = Authorize.get_jwt_subject()
    await assert_trek_owner(db, trek_id, user_id)
    await queries.delete_trek(db, trek_id=trek_id)
