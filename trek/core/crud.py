import base64
import logging
import typing as t

from colorhash import ColorHash
from cryptography.fernet import Fernet
from geopy.distance import distance
import pendulum
import polyline
import pyarrow as pa
import pyarrow.compute as pc
from pydantic import BaseModel, Field

from trek import config
from trek import exceptions as exc
from trek.core.core_utils import (
    assert_trek_exists,
    assert_trek_owner,
    assert_trek_participant,
    get_next_leg_adder,
    is_trek_participant,
)
from trek.database import Database, trek_schema, trek_user_schema, waypoint_schema
from trek.models import Id, Leg, Location, OutputName, Trek, TrekUser, Waypoint
from trek.utils import round_coords

log = logging.getLogger(__name__)


def _encrypt_id(trek_id: Id) -> str:
    id_as_bytes = str(trek_id).encode()
    encrypted = Fernet(config.fernet_key).encrypt(id_as_bytes)
    url_safe = base64.urlsafe_b64encode(encrypted).decode()
    return url_safe


def _decrypt_id(url_safe_encrypted_trek_id: str) -> Id:
    encrypted = base64.urlsafe_b64decode(url_safe_encrypted_trek_id.encode())
    trek_id_bytes = Fernet(config.fernet_key).decrypt(encrypted)
    trek_id = Id(trek_id_bytes.decode())
    return trek_id


def _get_user_color(index: int, user_id: Id) -> str:
    # https://iamkate.com/data/12-bit-rainbow/
    colors = [
        "#2cb",
        # "#0bc",
        # "#09c",
        "#36b",
        "#639",
        "#817",
        # "#a35",
        "#c66",
        "#e94",
        "#ed0",
        "#9d5",
        # "#4d8",
    ]
    try:
        return colors[index]
    except IndexError:
        return ColorHash(user_id).hex


def _generate_and_add_trek_user_record(db: Database, trek_id: Id, user_id: Id) -> None:
    trek_user_table = db.load_table(TrekUser)
    user_index = trek_user_table.filter(
        pc.field("trek_id") == pc.scalar(trek_id)
    ).num_rows
    user_color = _get_user_color(user_index, user_id)

    now = pendulum.now("utc")
    trek_user_record: TrekUser = {
        "trek_id": trek_id,
        "user_id": user_id,
        "added_at": now,
        "color": user_color,
    }
    record_table = pa.Table.from_pylist([trek_user_record], schema=trek_user_schema)
    merged_table = pa.concat_tables([trek_user_table, record_table])
    db.save_table(TrekUser, merged_table)


class GenerateInviteResponse(BaseModel):
    invite_id: t.Annotated[Id, Field(description="Encrypted invite id")]


def generate_trek_invite(trek_id: Id, user_id: Id, db: Database):
    assert_trek_owner(db, trek_id, user_id)
    encrypted_trek_id = _encrypt_id(trek_id)
    return GenerateInviteResponse(**{"invite_id": encrypted_trek_id})


class JoinTrekResponse(BaseModel):
    trek_id: Id


def add_user_to_trek(encrypted_trek_id: str, db: Database, user_id: Id):
    trek_id = _decrypt_id(encrypted_trek_id)
    assert_trek_exists(db, trek_id)
    if not is_trek_participant(db, trek_id, user_id):
        _generate_and_add_trek_user_record(db, trek_id, user_id)
    else:
        log.info(f"User {user_id} is alread participant in trek {trek_id}")
    return JoinTrekResponse(trek_id=trek_id)


def _toggle_trek_is_active(is_active: bool, trek_id: Id, user_id: Id, db: Database):
    assert_trek_exists(db, trek_id)
    assert_trek_owner(db, trek_id, user_id)
    trek_records = db.load_records(Trek)
    updated_trek_records = [
        record | {"is_active": is_active} if record["id"] == trek_id else record
        for record in trek_records
    ]
    updated_trek_table = pa.Table.from_pylist(updated_trek_records, schema=trek_schema)
    db.save_table(Trek, updated_trek_table)


def activate_trek(trek_id: Id, user_id: Id, db: Database):
    _toggle_trek_is_active(is_active=True, trek_id=trek_id, user_id=user_id, db=db)


def deactivate_trek(trek_id: Id, user_id: Id, db: Database):
    _toggle_trek_is_active(is_active=False, trek_id=trek_id, user_id=user_id, db=db)


class AddTrekRequest(BaseModel):
    polyline: str
    progress_at_hour: t.Annotated[int, Field(ge=0, le=23)] = 12
    progress_at_tz: str = "CET"
    output_to: t.Optional[OutputName] = None


class AddTrekResponse(BaseModel):
    trek_id: Id


def add_trek(
    request: AddTrekRequest,
    db: Database,
    user_id: Id,
) -> AddTrekResponse:
    trek_id = db.make_id()
    trek_record: Trek = {
        "id": trek_id,
        "owner_id": user_id,
        "is_active": False,
        "progress_at_hour": request.progress_at_hour,
        "progress_at_tz": request.progress_at_tz,
        "output_to": request.output_to,
    }
    db.append_record(Trek, trek_record)

    _generate_and_add_trek_user_record(db, trek_id, user_id)

    leg_id = db.make_id()
    leg_record: Leg = {
        "id": leg_id,
        "trek_id": trek_id,
        "added_at": pendulum.now("utc"),
        "added_by": user_id,
        "is_finished": False,
    }
    db.append_record(Leg, leg_record)

    waypoints = polyline.decode(request.polyline, 5)
    waypoint_records = _waypoint_tuple_to_records(trek_id, leg_id, waypoints, db)
    waypoints_table = pa.Table.from_pylist(waypoint_records, schema=waypoint_schema)
    db.save_table(Waypoint, waypoints_table)

    return AddTrekResponse(trek_id=trek_id)


class GetTrekResponse(BaseModel):
    users: list[str]
    legs: list[Leg]
    current_location: t.Union[Waypoint, Location, None]
    is_owner: bool
    is_active: bool
    can_add_leg: bool


def get_trek(
    trek_id: Id,
    db: Database,
    user_id: Id,
) -> GetTrekResponse:
    trek_table = db.load_table(Trek, filter=pc.field("id") == pc.scalar(trek_id))
    if trek_table.num_rows == 0:
        raise exc.ServerException(
            exc.E101Error(status_code=403, detail="Trek not found")
        )
    assert trek_table.num_rows == 1
    trek_record = trek_table.to_pylist()[0]

    trek_user_table = db.load_table(
        TrekUser, filter=(pc.field("trek_id") == pc.scalar(trek_id))
    )

    if trek_user_table.filter(pc.field("user_id") == pc.scalar(user_id)).num_rows == 0:
        raise exc.ServerException(exc.E101Error(status_code=403, detail="Forbidden"))

    trek_user_records: list[TrekUser] = trek_user_table.to_pylist()
    user_ids = [user["user_id"] for user in trek_user_records]

    is_owner = trek_record["owner_id"] == user_id

    leg_table = db.load_table(
        Leg, filter=pc.field("trek_id") == pc.scalar(trek_id)
    ).sort_by("added_at")
    leg_records = leg_table.to_pylist()

    can_add_leg = (not _check_unfinished_leg(leg_table)) and _check_is_next_leg_adder(
        trek_user_records, leg_table, user_id
    )

    locations_table = db.load_table(
        Location, filter=pc.field("trek_id") == pc.scalar(trek_id)
    ).sort_by([("added_at", "descending")])
    if locations_table.num_rows > 0:
        current_location = locations_table.slice(length=1).to_pylist()[0]
    else:
        waypoints_table = db.load_table(
            Waypoint, filter=pc.field("trek_id") == pc.scalar(trek_id)
        )
        current_location = waypoints_table.slice(length=1).to_pylist()[0]

    res = GetTrekResponse(
        legs=leg_records,
        is_owner=is_owner,
        users=user_ids,
        current_location=current_location,
        can_add_leg=can_add_leg,
        **trek_record,
    )
    return res


class EditTrekRequest(BaseModel):
    owner_id: t.Optional[Id] = None
    is_active: t.Optional[bool] = None
    progress_at_hour: t.Annotated[t.Optional[int], Field(ge=0, le=23)] = None
    progress_at_tz: t.Optional[str] = None
    output_to: t.Optional[OutputName] = None


def edit_trek(
    request: EditTrekRequest,
    trek_id: Id,
    db: Database,
    user_id: Id,
) -> None:
    assert_trek_exists(db, trek_id)
    assert_trek_owner(db, trek_id, user_id)
    trek_table = db.load_table(Trek)
    trek_filter = pc.field("id") == pc.scalar(trek_id)
    trek_record = trek_table.filter(trek_filter).to_pylist()[0]
    new_trek_data = request.dict(exclude_none=True, exclude_unset=True)
    trek_record.update(**new_trek_data)
    record_table = pa.Table.from_pylist([trek_record], schema=trek_schema)
    other_treks_table = trek_table.filter(~trek_filter)
    merged_table = pa.concat_tables([other_treks_table, record_table])
    db.save_table(Trek, merged_table)


class AddLegRequest(BaseModel):
    polyline: str


class AddLegResponse(BaseModel):
    leg_id: Id


def _check_unfinished_leg(leg_table: pa.Table):
    return leg_table.filter(~pc.field("is_finished")).num_rows > 0


def _assert_no_unfinished_leg(leg_table: pa.Table):
    if _check_unfinished_leg(leg_table):
        raise exc.ServerException(
            exc.E101Error(status_code=400, detail="Trek has unfinished leg")
        )


def _check_is_next_leg_adder(
    trek_users: list[TrekUser], leg_table: pa.Table, user_id: Id
):
    try:
        most_recent_adder_id = leg_table.column("added_by").to_pylist()[-1]
    except IndexError:
        next_adder_id = trek_users[0]["user_id"]
    else:
        next_adder_id = get_next_leg_adder(most_recent_adder_id, trek_users)
    return user_id == next_adder_id


def _assert_is_next_leg_adder(
    trek_users: list[TrekUser], leg_table: pa.Table, user_id: Id
):
    if not _check_is_next_leg_adder(trek_users, leg_table, user_id):
        raise exc.ServerException(
            exc.E101Error(status_code=400, detail="User is not in line to add leg")
        )


def _assert_waypoints_connect(
    db: Database, leg_table: pa.Table, trek_id: Id, waypoints: t.Sequence[tuple]
):
    prev_leg_id = leg_table.column("id").to_pylist()[-1]
    prev_leg_waypoints_table = db.load_table(
        Waypoint,
        filter=(
            (pc.field("trek_id") == pc.scalar(trek_id))
            & (pc.field("leg_id") == pc.scalar(prev_leg_id))
        ),
    )
    last_loc_record = prev_leg_waypoints_table.sort_by("distance").to_pylist()[-1]
    last_loc_tuple = (int(last_loc_record["lat"]), int(last_loc_record["lon"]))
    first_loc = waypoints[0]
    first_loc_tuple = (int(first_loc[0]), int(first_loc[1]))
    if last_loc_tuple != first_loc_tuple:
        raise exc.ServerException(
            exc.E101Error(
                status_code=400,
                detail=f"Leg does not start where last ended - {last_loc_tuple} vs {first_loc_tuple}",
            )
        )


def add_leg(
    trek_id: Id,
    request: AddLegRequest,
    db: Database,
    user_id: Id,
) -> AddLegResponse:
    assert_trek_exists(db, trek_id)
    assert_trek_participant(db, trek_id, user_id)
    leg_table = db.load_table(
        Leg, filter=pc.field("trek_id") == pc.scalar(trek_id)
    ).sort_by("added_at")

    _assert_no_unfinished_leg(leg_table)
    trek_users = db.load_records(
        TrekUser, filter=pc.field("trek_id") == pc.scalar(trek_id)
    )
    _assert_is_next_leg_adder(trek_users, leg_table, user_id)
    waypoints = polyline.decode(request.polyline, 5)
    if leg_table.num_rows > 0:
        _assert_waypoints_connect(db, leg_table, trek_id, waypoints)

    leg_id = db.make_id()
    leg_record: Leg = {
        "id": leg_id,
        "trek_id": trek_id,
        "added_at": pendulum.now("utc"),
        "added_by": user_id,
        "is_finished": False,
    }
    db.append_record(Leg, leg_record)

    waypoint_records = _waypoint_tuple_to_records(trek_id, leg_id, waypoints, db)
    waypoints_table = pa.Table.from_pylist(waypoint_records, schema=waypoint_schema)
    db.save_table(Waypoint, waypoints_table)

    return AddLegResponse(leg_id=leg_id)


def _waypoint_tuple_to_records(
    trek_id: Id, leg_id: Id, waypoints: list[tuple[float, float]], db: Database
) -> list[Waypoint]:
    result = []
    lat, lon = waypoints[0]
    first_waypoint: Waypoint = {
        "id": db.make_id(),
        "trek_id": trek_id,
        "leg_id": leg_id,
        "lat": round_coords(lat),
        "lon": round_coords(lon),
        "distance": 0,
    }
    result.append(first_waypoint)
    prev_waypoint = first_waypoint
    for lat, lon in waypoints[1:]:
        distance_from_prev = distance(
            (prev_waypoint["lat"], prev_waypoint["lon"]),
            (lat, lon),
        ).m
        distance_from_prev = round(distance_from_prev, 2)
        cumulative_distance = prev_waypoint["distance"] + distance_from_prev
        waypoint: Waypoint = {
            "id": db.make_id(),
            "trek_id": trek_id,
            "leg_id": leg_id,
            "lat": round_coords(lat),
            "lon": round_coords(lon),
            "distance": cumulative_distance,
        }
        result.append(waypoint)
        prev_waypoint = waypoint
    return result


def delete_trek(trek_id: Id, db: Database, user_id: Id):
    assert_trek_exists(db, trek_id)
    assert_trek_owner(db, trek_id, user_id)
    db.delete_records(Trek, filter=pc.field("id") == pc.scalar(trek_id))
    filter_ = pc.field("trek_id") == pc.scalar(trek_id)
    db.delete_records(Leg, filter=filter_)
    db.delete_records(Location, filter=filter_)
    db.delete_records(TrekUser, filter=filter_)
    db.delete_partion(Waypoint, trek_id)


class GetLegResponse(BaseModel):
    leg: Leg
    locations: list[Location]
    start: t.Optional[dict]
    end: t.Optional[dict]
    polyline: t.Optional[str]


def get_leg(
    trek_id: Id,
    leg_id: Id,
    db: Database,
    user_id: Id,
) -> GetLegResponse:
    assert_trek_exists(db, trek_id)
    assert_trek_participant(db, trek_id, user_id)
    try:
        leg_record = db.load_records(
            Leg,
            filter=(pc.field("trek_id") == pc.scalar(trek_id))
            & (pc.field("id") == pc.scalar(leg_id)),
        )[0]
    except IndexError:
        raise exc.ServerException(
            exc.E101Error(status_code=403, detail="Leg not found")
        )
    locations = db.load_records(
        Location,
        filter=(pc.field("trek_id") == pc.scalar(trek_id))
        & (pc.field("leg_id") == pc.scalar(leg_id)),
    )

    if len(locations) == 0:
        line = None
        start = None
        end = None
    else:
        waypoints_filter = (pc.field("trek_id") == pc.scalar(trek_id)) & (
            pc.field("leg_id") == pc.scalar(leg_id)
        )
        if not leg_record["is_finished"]:
            waypoints_filter = waypoints_filter & (
                pc.field("distance") < locations[-1]["distance"]
            )
        waypoints = db.load_records(
            Waypoint, filter=waypoints_filter, columns=["lat", "lon"]
        )
        line = polyline.encode(
            [(waypoint["lat"], waypoint["lon"]) for waypoint in waypoints], 5
        )
        start = waypoints[0]
        end = waypoints[-1]

    res = GetLegResponse(
        leg=leg_record,
        locations=locations,
        polyline=line,
        start=start,
        end=end,
    )
    return res
