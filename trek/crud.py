from __future__ import annotations

import base64
import datetime as dt
import logging

import aiosql
import asyncpg
from cryptography.fernet import Fernet
from databases import Database
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi_jwt_auth import AuthJWT
from geopy.distance import distance
import pendulum
from pydantic import BaseModel, Field

from trek import config
from trek.database import DatabasesAdapter, get_db
from trek.utils import protect_endpoint

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/trek", tags=["treks"], dependencies=[Depends(protect_endpoint)]
)
queries = aiosql.from_path("sql/crud.sql", DatabasesAdapter)
waypointsField = Field(
    ...,
    description="List of tuples containing 3 floats: lat, lon and elevation",
    example=[
        [10.671114, 59.332889, 18.35],
        [10.671664, 59.333243, 18.31],
        [10.671857, 59.333329, 18.32],
        [10.672099, 59.333292, 17.51],
    ],
)


async def assert_trek_owner(db: Database, trek_id: int, user_id: int) -> None:
    if not await queries.is_trek_owner(db, trek_id=trek_id, user_id=user_id):
        raise HTTPException(status_code=403, detail="Forbidden")


async def assert_trek_participant(db: Database, trek_id: int, user_id: int) -> None:
    if not await queries.is_trek_participant(db, trek_id=trek_id, user_id=user_id):
        raise HTTPException(status_code=403, detail="Forbidden")


def encrypt_id(trek_id: int) -> str:
    id_as_bytes = str(trek_id).encode()
    encrypted = Fernet(config.fernet_key).encrypt(id_as_bytes)
    url_safe = base64.urlsafe_b64encode(encrypted).decode()
    return url_safe


def decrypt_id(url_safe_encrypted_trek_id: str) -> int:
    encrypted = base64.urlsafe_b64decode(url_safe_encrypted_trek_id.encode())
    trek_id_bytes = Fernet(config.fernet_key).decrypt(encrypted)
    trek_id = int(trek_id_bytes.decode())
    return trek_id


class GenerateInviteResponse(BaseModel):
    invite_id: str = Field(..., description="Encrypted invite id")


@router.get(
    "/invite/{trek_id}/",
    response_model=GenerateInviteResponse,
    operation_id="authorize",
)
async def generate_trek_invite(
    trek_id: int,
    db: Database = Depends(get_db),
    Authorize: AuthJWT = Depends(),
):
    user_id = Authorize.get_jwt_subject()
    await assert_trek_owner(db, trek_id, user_id)
    encrypted_trek_id = encrypt_id(trek_id)
    return {"invite_id": encrypted_trek_id}


@router.get("/join/{encrypted_trek_id}/", operation_id="authorize")
async def add_user_to_trek(
    encrypted_trek_id: str,
    db: Database = Depends(get_db),
    Authorize: AuthJWT = Depends(),
):
    trek_id = decrypt_id(encrypted_trek_id)
    user_id = Authorize.get_jwt_subject()
    now = dt.datetime.fromtimestamp(pendulum.now().timestamp(), pendulum.tz.UTC)
    try:
        await queries.add_trek_user(db, trek_id=trek_id, user_id=user_id, added_at=now)
    except asyncpg.exceptions.UniqueViolationError:
        # user already in trek
        return Response(status_code=200)
    # except other exception: trek does not exists
    return Response(status_code=201)


class AddRequest(BaseModel):
    origin: str
    destination: str
    waypoints: list = waypointsField


class AddResponse(BaseModel):
    trek_id: int
    leg_id: int


@router.post("/", response_model=AddResponse, operation_id="authorize")
async def add_trek(
    request: AddRequest,
    db: Database = Depends(get_db),
    Authorize: AuthJWT = Depends(),
):
    user_id = Authorize.get_jwt_subject()
    trek_record = await queries.add_trek(db, origin=request.origin, owner_id=user_id)
    trek_id = trek_record["id"]
    leg_record = await queries.add_leg(
        db,
        trek_id=trek_id,
        destination=request.destination,
        added_at=pendulum.now("utc"),
        added_by=user_id,
    )
    leg_id = leg_record["id"]
    waypoints_in = waypoint_tuple_to_dicts(trek_id, leg_id, request.waypoints)
    await queries.add_waypoints(db, waypoints_in)
    now = dt.datetime.fromtimestamp(pendulum.now().timestamp(), pendulum.tz.UTC)
    await queries.add_trek_user(db, user_id=user_id, trek_id=trek_id, added_at=now)
    return {"trek_id": trek_id, "leg_id": leg_id}


class Leg(BaseModel):
    id: int
    destination: str
    added_at: pendulum.DateTime


class GetResponse(BaseModel):
    origin: str
    users: list[int]
    legs: list[Leg]
    is_owner: bool


@router.get("/{trek_id}", response_model=GetResponse, operation_id="authorize")
async def get_trek(
    trek_id: int,
    db: Database = Depends(get_db),
    Authorize: AuthJWT = Depends(),
):
    user_id = Authorize.get_jwt_subject()
    await assert_trek_participant(db, trek_id, user_id)
    is_owner = await queries.is_trek_owner(db, trek_id=trek_id, user_id=user_id)
    trek_data = await queries.get_trek(db, trek_id=trek_id)
    legs = await queries.get_legs_for_trek(db, trek_id=trek_id)
    record = GetResponse(legs=legs, is_owner=is_owner, **trek_data)
    return record


class AddLegRequest(BaseModel):
    destination: str
    waypoints: list = waypointsField


class AddLegResponse(BaseModel):
    leg_id: int


@router.post(
    "/{trek_id}",
    operation_id="authorize",
    response_model=AddLegResponse,
)
async def add_leg(
    trek_id: int,
    request: AddLegRequest,
    db: Database = Depends(get_db),
    Authorize: AuthJWT = Depends(),
):
    user_id = Authorize.get_jwt_subject()
    await assert_trek_participant(db, trek_id, user_id)
    legs = await queries.get_legs_for_trek(db, trek_id=trek_id)
    prev_lev = legs[-1]
    if prev_lev["is_ongoing"]:
        raise HTTPException(status_code=400, detail="Trek has ongoing leg")
    prev_adder_id = await queries.prev_adder_id(db, leg_id=prev_lev["id"])
    next_adder_id = await queries.next_adder_id(
        db, prev_adder_id=prev_adder_id, trek_id=trek_id
    )
    if user_id != next_adder_id:
        raise HTTPException(status_code=400, detail="User is not in line to add leg")
    last_loc = await queries.get_last_waypoint_for_leg(db, leg_id=prev_lev["id"])
    last_loc_tuple = [last_loc["lat"], last_loc["lon"], last_loc["elevation"]]
    first_loc = request.waypoints[0]
    if last_loc_tuple != first_loc:
        raise HTTPException(
            status_code=400, detail="Leg does not start where last ended"
        )

    leg_record = await queries.add_leg(
        db,
        trek_id=trek_id,
        destination=request.destination,
        added_at=pendulum.now("utc"),
        added_by=user_id,
    )
    leg_id = leg_record["id"]
    waypoints_in = waypoint_tuple_to_dicts(trek_id, leg_id, request.waypoints)
    await queries.add_waypoints(db, waypoints_in)
    await queries.start_leg(db, id=leg_id)
    return AddLegResponse(leg_id=leg_id)


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


@router.delete("/{trek_id}", operation_id="authorize")
async def delete_trek(
    trek_id: int,
    db: Database = Depends(get_db),
    Authorize: AuthJWT = Depends(),
):
    user_id = Authorize.get_jwt_subject()
    await assert_trek_owner(db, trek_id, user_id)
    await queries.delete_trek(db, trek_id=trek_id)
