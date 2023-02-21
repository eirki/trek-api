import logging
import typing as t

from fastapi import APIRouter, Query
import openrouteservice

from trek import config
from trek.core import search

log = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])
ors_client = openrouteservice.Client(key=config.ors_key)


@router.get(
    "/locations",
)
def locations(
    query: str = Query(
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
    ),
) -> search.LocationResult:
    return search.locations(query)


coord_desc = "Comma-separated lat lon coordinates"


@router.get("/route")
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
) -> search.RouteResult:
    return search.route(start, stop, via, skip_segments)
