import typing as t

import pendulum
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds

Id = t.NewType("Id", str)
OutputName = t.Literal["telegram", "discord"]
TrackerName = t.Literal["fitbit", "withings", "googlefit", "polar"]


class User(t.TypedDict):
    id: Id
    name: t.Optional[str]
    is_admin: bool
    active_tracker: t.Optional[TrackerName]


class UserToken(t.TypedDict):
    token: str
    user_id: Id
    tracker_name: TrackerName
    tracker_user_id: Id


class TrekUser(t.TypedDict):
    trek_id: Id
    user_id: Id
    added_at: pendulum.DateTime
    color: str


class DiscordChannel(t.TypedDict):
    trek_id: Id
    guild_id: t.Annotated[int, pa.uint64()]
    channel_id: t.Annotated[int, pa.uint64()]


class PolarCache(t.TypedDict):
    user_id: Id
    n_steps: t.Annotated[int, pa.uint32()]
    created_at: pendulum.Date
    taken_at: pendulum.Date


class Trek(t.TypedDict):
    id: Id
    owner_id: Id
    is_active: bool
    progress_at_hour: t.Annotated[int, pa.uint8()]
    progress_at_tz: str
    output_to: t.Optional[OutputName]


trek_validators = [
    (pc.field("progress_at_hour") >= pc.scalar(0))
    & (pc.field("progress_at_hour") <= pc.scalar(23))
]


class Leg(t.TypedDict):
    id: Id
    trek_id: Id
    added_at: pendulum.DateTime
    added_by: Id
    is_finished: bool


class Waypoint(t.TypedDict):
    id: Id
    trek_id: Id
    leg_id: Id
    lat: t.Annotated[float, pa.float64()]
    lon: t.Annotated[float, pa.float64()]
    # elevation: t.Annotated[t.Optional[float], pa.float64()]
    distance: t.Annotated[float, pa.float64()]


waypoints_partitioning = ds.partitioning(
    schema=pa.schema(
        [
            pa.field("trek_id", pa.string(), nullable=False),
            pa.field("leg_id", pa.string(), nullable=False),
        ]
    )
)


class Location(t.TypedDict):
    trek_id: Id
    leg_id: Id
    added_at: pendulum.Date
    latest_waypoint: Id
    lat: t.Annotated[float, pa.float64()]
    lon: t.Annotated[float, pa.float64()]
    distance: t.Annotated[float, pa.float64()]
    address: t.Optional[str]
    country: t.Optional[str]
    is_new_country: t.Optional[bool]
    is_last_in_leg: t.Optional[bool]
    poi: t.Optional[str]
    photo_url: t.Optional[str]
    gmap_url: t.Optional[str]
    traversal_map_url: t.Optional[str]
    achievements: t.Annotated[t.Optional[list[Id]], pa.list_(value_type=pa.string())]
    factoid: t.Optional[str]


class Step(t.TypedDict):
    trek_id: Id
    leg_id: Id
    user_id: Id
    taken_at: pendulum.Date
    amount: t.Annotated[int, pa.uint32()]


class Achievement(t.TypedDict):
    id: Id
    added_at: pendulum.Date
    amount: t.Annotated[int, pa.uint32()]
    user_id: Id
    old_added_at: pendulum.Date
    old_amount: t.Annotated[int, pa.uint32()]
    old_user_id: Id
    is_for_trek: bool
    achievement_type: str
    description: str
    unit: str
