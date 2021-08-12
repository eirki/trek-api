from __future__ import annotations

import logging
import typing as t

import aiosql
from databases import Database
from fastapi import APIRouter, Depends
from geopy.distance import distance
import pendulum
from pydantic import BaseModel, Field

from trek.database import DatabasesAdapter, get_db

log = logging.getLogger(__name__)
router = APIRouter(prefix="/trek")
queries = aiosql.from_path("sql/trek.sql", DatabasesAdapter)


class AddRequest(BaseModel):
    origin: str
    destination: str
    waypoints: list = Field(
        ..., description="List of tuples containing 3 floats: lat, lon and elevation"
    )
    users: list[int]


@router.post("/")
async def add_trek(request: AddRequest, db: Database = Depends(get_db)):
    trek_record = await queries.add_trek(
        db, origin=request.origin, destination=request.destination
    )
    trek_id = trek_record["id"]
    lat, lon, elevation = request.waypoints[0]
    first_waypoint = {
        "trek_id": trek_id,
        "lat": lat,
        "lon": lon,
        "elevation": elevation,
        "distance": 0,
    }
    waypoints_in = [first_waypoint]
    prev_waypoint = first_waypoint
    for lat, lon, elevation in request.waypoints[1:]:
        distance_from_prev = distance(
            (prev_waypoint["lat"], prev_waypoint["lon"]),
            (lat, lon),
        ).m
        cumulative_distance = prev_waypoint["distance"] + distance_from_prev
        waypoint = {
            "trek_id": trek_id,
            "lat": lat,
            "lon": lon,
            "elevation": elevation,
            "distance": cumulative_distance,
        }
        waypoints_in.append(waypoint)
        prev_waypoint = waypoint
    await queries.add_waypoints(db, waypoints_in)
    users_in = [{"trek_id": trek_id, "user_id": user_id} for user_id in request.users]
    await queries.add_trek_users(db, users_in)
    return {"trek_id": trek_id}


class GetResponse(BaseModel):
    id: int
    origin: str
    destination: str
    ongoing: bool
    started_at: t.Optional[pendulum.Date]
    users: list[int]


@router.get("/{trek_id}", response_model=GetResponse)
async def get_trek(trek_id: int, db: Database = Depends(get_db)):
    trek_data = await queries.get_trek(db, trek_id=trek_id)
    record = GetResponse(**trek_data)
    return record


class ExtendRequest(BaseModel):
    trek_id: int
    destination: str
    waypoints: list = Field(
        ..., description="List of tuples containing 3 floats: lat, lon and elevation"
    )


@router.post("/{trek_id}")
async def extend_trek(request: ExtendRequest):
    ...


@router.delete("/{trek_id}")
async def delete_trek(trek_id: int, db: Database = Depends(get_db)):
    await queries.delete_trek(db, trek_id=trek_id)
