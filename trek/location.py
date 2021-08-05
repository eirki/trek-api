from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.params import Query
import geopy
from geopy.geocoders import Nominatim
from pydantic import BaseModel, Field

from trek.utils import raise_http_exc

log = logging.getLogger(__name__)
router = APIRouter()
geolocator = Nominatim(user_agent="trek")

address_fields = ["road", "house_name", "house_number"]
location_fields = [
    "city_district",
    "district",
    "borough",
    "suburb",
    "subdivision",
    "municipality",
    "city",
    "town",
    "village",
    "region",
    "state",
    "state_district",
    "county",
    "province",
    "country",
]


class Location(BaseModel):
    name: str = Field(..., example="Larkollveien")
    context: str = Field(..., example="Dilling, Moss, Viken, Norway")
    latitude: float = Field(..., example=59.40)
    longitude: float = Field(..., example=10.69)
    type: str = Field(..., example="primary")


class Result(BaseModel):
    locations: list[Location]


def address_context(location_data: dict, fields: list[str]) -> str:
    # https://nominatim.org/release-docs/develop/api/Output/#addressdetails
    return ", ".join(
        [location_data[field] for field in fields if field in location_data]
    )


def address_name(location_data: dict) -> str:
    namedetails = location_data["namedetails"]
    try:
        return namedetails["name:en"]
    except KeyError:
        pass
    try:
        return namedetails["name"]
    except KeyError:
        pass
    return address_context(location_data["address"], address_fields)


def geopy_to_location_result(location: geopy.Location) -> Location:
    return Location(
        name=address_name(location.raw),
        context=address_context(location.raw["address"], location_fields),
        latitude=location.latitude,
        longitude=location.longitude,
        type=location.raw.get("type"),
    )


def location_query(query: str) -> list[geopy.Location] | None:  # no test coverage
    log.info(f"location query: {query}")
    try:
        return geolocator.geocode(
            query,
            exactly_one=False,
            addressdetails=True,
            namedetails=True,
            language="en",
        )
    except Exception as e:
        log.exception("Geolocator error", exc_info=True)
        raise_http_exc(e, message="GeocoderUnavailable")


@router.get("/locations", responses={200: {"model": Result}})
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
) -> Result:
    query = query.lower()
    location_data = location_query(query)
    locations = (
        [geopy_to_location_result(loc) for loc in location_data]
        if location_data is not None
        else []
    )
    # TODO: remove duplicates
    res = Result(locations=locations)
    return res
