from __future__ import annotations

import logging
import typing as t

from fastapi import APIRouter, Query
import openrouteservice
from pydantic import BaseModel, Field

from trek import config

log = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])
ors_client = openrouteservice.Client(key=config.ors_key)


class Location(BaseModel):
    name: str = Field(..., example="Larkollveien")
    latitude: float = Field(..., example=59.40)
    longitude: float = Field(..., example=10.69)


class LocationResult(BaseModel):
    locations: list[Location]


@router.get("/locations", responses={200: {"model": LocationResult}})
async def locations(
    query=Query(
        ...,
        examples={
            "Name": {
                "description": "Location name (partial or full)",
                "value": "Larkoll",
            },
            "Coordinates": {
                "description": "Comma-separated lat lon coordinates",
                "value": "59.333289,10.671775",
            },
        },
    )
) -> LocationResult:
    try:
        lat, lon = [float(q) for q in query.split(",")]
    except ValueError:
        search_result = ors_client.pelias_autocomplete(text=query)
    else:
        search_result = ors_client.pelias_reverse(point=[lon, lat])
    location_data = search_result["features"]
    locations = [
        Location(
            name=loc["properties"]["label"],
            latitude=loc["geometry"]["coordinates"][1],
            longitude=loc["geometry"]["coordinates"][0],
        )
        for loc in location_data
    ]
    res = LocationResult(locations=locations)
    return res


class Coordinates(BaseModel):
    lat: float
    lon: float

    @classmethod
    def from_string(cls, data: str):
        lat, lon = data.split(",")
        return cls(lat=lat, lon=lon)


class Points(BaseModel):
    type: str
    coordinates: list = Field(
        ..., description="List of tuples containing 3 floats: lon, lat and elevation"
    )


class Route(BaseModel):
    bbox: list[float]
    distance: float
    points: Points

    class Config:
        schema_extra = {
            "bbox": [10.669837, 59.331706, 0, 10.673249, 59.333329, 0],
            "distance": 552,
            "points": {
                "type": "LineString",
                "coordinates": [
                    [10.673249, 59.331706, 0],
                    [10.669838, 59.332407, 0],
                    [10.670007, 59.332392, 15],
                    [10.670262, 59.332435, 15.5],
                    [10.670424, 59.332482, 15.8],
                    [10.670682, 59.33261, 16.2],
                    [10.671047, 59.332845, 16.8],
                    [10.671664, 59.333243, 19.1],
                    [10.671857, 59.333329, 19.2],
                    [10.671895, 59.333323, 19.8],
                ],
            },
        }


class RouteResult(BaseModel):
    route: Route


coord_desc = "Comma-separated lat lon coordinates"


@router.get("/route", responses={200: {"model": RouteResult}})
async def route(
    start: str = Query(..., example="59.3317064, 10.673249", description=coord_desc),
    stop: str = Query(..., example="59.3333289, 10.6718981", description=coord_desc),
    via: t.Optional[list[str]] = Query(
        None,
        example=[
            "59.3324068, 10.6698381",
            "59.33282, 10.6711095",
        ],
        description=f"List of {coord_desc.lower()}",
    ),
    skip_segments: list[int] = Query(
        None,
        example=[1],
        description=(
            "Specifies the segments that should be skipped in the route calculation. "
            "A segment is the connection between two given coordinates and the counting "
            "starts with 1 for the connection between the first and second coordinate."
        ),
    ),
):
    locations = []
    locations.append(Coordinates.from_string(start))
    if via:
        locations.extend([Coordinates.from_string(point) for point in via])
    locations.append(Coordinates.from_string(stop))

    search_result = ors_client.directions(
        coordinates=[[loc.lon, loc.lat] for loc in locations],
        skip_segments=skip_segments,
        options={"avoid_features": ["highways"]},
        elevation=True,
        format="geojson",
        instructions=False,
    )
    if len(search_result["features"]) == 0:
        raise Exception
    route_data = search_result["features"][0]
    route = Route(
        bbox=route_data["bbox"],
        distance=route_data["properties"]["summary"]["distance"],
        points=route_data["geometry"],
    )
    result = RouteResult(route=route)
    return result
