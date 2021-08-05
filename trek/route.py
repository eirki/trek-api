from __future__ import annotations

import logging
import typing as t

from fastapi import APIRouter, Query
import httpx
from pydantic import BaseModel, Field

from trek import env
from trek.utils import raise_http_exc

log = logging.getLogger(__name__)
router = APIRouter()


class Coordinates(BaseModel):
    lat: float
    lon: float

    @classmethod
    def from_string(cls, data: str):
        lat, lon = data.split(",")
        return cls(lat=lat, lon=lon)


class GraphhopperPoints(BaseModel):
    type: str
    coordinates: list = Field(
        ..., description="List of tuples containing 3 floats: lat, lon and elevation"
    )


class GraphhopperRoute(BaseModel):
    time: int
    bbox: list[float] = Field(..., min_items=4, max_items=4)
    distance: float
    # weight: float
    # transfers: int
    # points_encoded: bool
    points: GraphhopperPoints

    class Config:
        schema_extra = {
            "example": {
                "time": 17796,
                "bbox": [10.671114, 59.332889, 10.672099, 59.333329],
                "distance": 79.101,
                "points": {
                    "type": "LineString",
                    "coordinates": [
                        [10.671114, 59.332889, 18.35],
                        [10.671664, 59.333243, 18.31],
                        [10.671857, 59.333329, 18.32],
                        [10.672099, 59.333292, 17.51],
                    ],
                },
            }
        }


class Result(BaseModel):
    route: GraphhopperRoute


def parse_graphopper_exceptions(data: dict) -> dict:
    if data["detail"]["details"].endswith("ConnectionNotFoundException"):
        return {"message": "ConnectionNotFound"}
    elif data["detail"]["details"].endswith("PointNotFoundException"):
        return {
            "message": "PointNotFound",
            "data": {"point_index": data["detail"]["point_index"]},
        }
    else:
        raise Exception("Unknown Graphopper error")


coord_desc = "Comma-separated lat lon coordinates"


@router.get("/route", responses={200: {"model": Result}})
async def route(
    start: str = Query(..., example="59.332889,10.671114", description=coord_desc),
    stop: str = Query(..., example="59.333292,10.672099", description=coord_desc),
    via: t.Optional[list[str]] = Query(
        None,
        example=["59.333122,10.671475", "59.333291,10.671772"],
        description=f"List of {coord_desc.lower()}",
    ),
):
    locations = []
    locations.append(Coordinates.from_string(start))
    if via:
        locations.extend([Coordinates.from_string(point) for point in via])
    locations.append(Coordinates.from_string(stop))

    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                env.graphopper_url,
                params={
                    "point": [f"{loc.lat},{loc.lon}" for loc in locations],
                    "elevation": True,
                    "key": env.graphhopper_api_key,
                    "type": "json",
                    "points_encoded": False,
                    "instructions": False,
                    "avoid": "motorway",
                },
            )
        data = res.json()
    except Exception as e:
        raise_http_exc(e)
    if res.status_code != 200:
        raise_http_exc(error=None, **parse_graphopper_exceptions(data))
    route_data = data["paths"][0]
    route = GraphhopperRoute(**route_data)
    return route
