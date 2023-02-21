import logging
import typing as t  # noqa

import openrouteservice
from openrouteservice.exceptions import ApiError
from pydantic import BaseModel, Field

from trek import config
from trek import exceptions as exc

log = logging.getLogger(__name__)
ors_client = openrouteservice.Client(key=config.ors_key)


class Location(BaseModel):
    name: str = Field(..., example="Larkollveien")
    latitude: float = Field(..., example=59.40)
    longitude: float = Field(..., example=10.69)


class LocationResult(BaseModel):
    locations: list[Location]


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
    polyline: str
    # points: Points

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
    success = True
    route: Route


def locations(query: str) -> LocationResult:
    try:
        try:
            lat, lon = [float(q) for q in query.split(",")]
        except ValueError:
            search_result = ors_client.pelias_autocomplete(text=query)
        else:
            search_result = ors_client.pelias_reverse(point=[lon, lat])
    except ApiError as e:
        try:
            desc = e.message.get("error", {}).get("message")
        except Exception:
            desc = None
        raise exc.ServerException(exc.E301SearchAPIError(description=desc))

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


def route(
    start: str, stop: str, via: t.Optional[list[str]], skip_segments: list[int]
) -> RouteResult:
    locations = [
        Coordinates.from_string(start),
        *([Coordinates.from_string(point) for point in via] if via is not None else []),
        Coordinates.from_string(stop),
    ]
    try:
        search_result = ors_client.directions(
            coordinates=[[loc.lon, loc.lat] for loc in locations],
            skip_segments=skip_segments,
            options={"avoid_features": ["highways"]},
            elevation=False,
            instructions=False,
            format="json",
            # format="geojson",
            # Default “json”. Geometry format for “json” is Google’s encodedpolyline.
            # geometry=False,
        )
    except ApiError as e:
        try:
            desc = e.message.get("error", {}).get("message")
        except Exception:
            desc = None
        raise exc.ServerException(exc.E301SearchAPIError(description=desc))
    if len(search_result.get("routes", [])) == 0:
        raise exc.ServerException(exc.E302NoRouteFound())
    route_data = search_result["routes"][0]
    distance = route_data["summary"]["distance"]

    if distance > config.max_route_distance:
        raise exc.ServerException(
            exc.E303RouteTooLong(
                route_length=distance, max_length=config.max_route_distance
            )
        )
    line = route_data["geometry"]
    route = Route(
        bbox=route_data["bbox"],
        distance=distance,
        # points=route_data["geometry"],
        polyline=line,
    )
    result = RouteResult(route=route)
    return result
