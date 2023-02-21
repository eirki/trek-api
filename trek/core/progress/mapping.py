from io import BytesIO
import logging
import typing as t

from PIL import Image, ImageChops, ImageDraw, ImageFont
import pendulum
from staticmap import CircleMarker, Line, StaticMap

from trek.core.progress import progress_utils
from trek.core.progress.progress_utils import UserProgress
from trek.core.progress.upload import UploadFunc
from trek.database import Database
from trek.models import Id, Location

log = logging.getLogger(__name__)


class Point(t.TypedDict):
    lat: float
    lon: float
    distance: float


PointT = tuple[float, float]
PointTList = list[PointT]


class MappingFunc(t.Protocol):
    def __call__(
        self,
        db: Database,
        trek_id: Id,
        leg_id: Id,
        date: pendulum.Date,
        last_location: t.Optional[Location],
        current_location: PointT,
        current_distance: float,
        users_progress: list[UserProgress],
        upload_func: UploadFunc,
    ) -> t.Optional[str]:
        ...


class UserPoint(t.TypedDict):
    points: PointTList
    user: UserProgress


list[tuple[UserProgress, PointTList]]


def _get_day_points(
    current_points: list[Point],
    last_location: t.Optional[Location],
    users_progress: list[UserProgress],
    start_dist: float,
) -> list[tuple[UserProgress, PointTList]]:
    day_points: list[tuple[UserProgress, PointTList]] = []
    waypoints_itr = iter(current_points)
    # starting location
    latest_waypoint: Point = (
        {
            "lat": last_location["lat"],
            "lon": last_location["lon"],
            "distance": last_location["distance"],
        }
        if last_location is not None
        else current_points[0]
    )
    current_distance = start_dist
    next_waypoint = None
    for user in users_progress:
        user_points: PointTList = []
        user_points.append((latest_waypoint["lon"], latest_waypoint["lat"]))
        user_distance: float = user["step"]["amount"] * progress_utils.STRIDE
        current_distance += user_distance
        while True:
            if next_waypoint is None or next_waypoint["distance"] < current_distance:
                # next_waypoint from previous users has been passed
                next_waypoint = next(waypoints_itr, None)
                if next_waypoint is None:
                    # leg finished, no next waypoint
                    break

            if next_waypoint["distance"] < current_distance:
                # next_waypoint passed by this user
                user_points.append((next_waypoint["lon"], next_waypoint["lat"]))
                latest_waypoint = next_waypoint
                continue
            elif next_waypoint["distance"] >= current_distance:
                # next_waypoint will not be passed by this user
                remaining_dist = current_distance - latest_waypoint["distance"]
                last_lat, last_lon = progress_utils.point_between_waypoints(
                    latest_waypoint, next_waypoint, remaining_dist
                )
                user_points.append((last_lon, last_lat))
                # assign starting location for next user
                latest_waypoint = {
                    "lat": last_lat,
                    "lon": last_lon,
                    "distance": current_distance,
                }
                break
        day_points.append((user, user_points))
    return day_points


def _traversal_data(
    db: Database,
    trek_id: Id,
    leg_id: Id,
    last_location: t.Optional[Location],
    current_lat: float,
    current_lon: float,
    current_distance: float,
    users_progress: list[UserProgress],
) -> tuple[PointTList, PointTList, PointTList, list[tuple[UserProgress, PointTList]]]:
    old_points: PointTList
    location_points: PointTList
    leg_points: PointTList
    # TODO: add older legs from same trek?
    if last_location is None:
        old_points = []
        location_points = []
        start_dist = 0.0
        leg_points = []
    else:
        old_waypoints = progress_utils.waypoints_between_distances(
            db,
            trek_id=trek_id,
            leg_id=leg_id,
            low=0,
            high=last_location["distance"],
        )
        old_points = [(loc["lon"], loc["lat"]) for loc in old_waypoints]
        old_points.append((last_location["lon"], last_location["lat"]))
        locations = progress_utils.locations_between_distances(
            db,
            trek_id=trek_id,
            leg_id=leg_id,
            low=0,
            high=last_location["distance"],
        )
        location_points = [(old_waypoints[0]["lon"], old_waypoints[0]["lat"])]
        location_points.extend([(loc["lon"], loc["lat"]) for loc in locations])
        start_dist = last_location["distance"]
        leg_points = [(last_location["lon"], last_location["lat"])]

    current_waypoints = progress_utils.waypoints_between_distances(
        db, trek_id=trek_id, leg_id=leg_id, low=start_dist, high=current_distance
    )
    current_points: list[Point] = [
        {"lat": point["lat"], "lon": point["lon"], "distance": point["distance"]}
        for point in current_waypoints
    ]
    current_points.append(
        {"lat": current_lat, "lon": current_lon, "distance": current_distance}
    )
    leg_points.extend([(loc["lon"], loc["lat"]) for loc in current_waypoints])
    leg_points.append((current_lon, current_lat))

    day_points = _get_day_points(
        current_points, last_location, users_progress, start_dist
    )
    return old_points, location_points, leg_points, day_points


def _map_legend(user_points: list[tuple[UserProgress, PointTList]]) -> Image.Image:
    def trim(im):
        bg = Image.new(im.mode, im.size, im.getpixel((0, 0)))
        diff = ImageChops.difference(im, bg)
        diff = ImageChops.add(diff, diff, 2.0, -100)
        bbox = diff.getbbox()
        if bbox:
            left, upper, right, lower = bbox
            return im.crop((left, upper - 5, right + 5, lower + 5))

    padding = 5
    line_height = 20
    img = Image.new("RGB", (1000, 1000), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("Pillow/Tests/fonts/DejaVuSans.ttf", line_height)
    for i, (user, _) in enumerate(user_points):
        current_line_height = (line_height + padding) * (i + 1)
        color = user["trek_user"]["color"]
        name = user["user"]["name"]
        draw.text(xy=(0, current_line_height), text="—", fill=color, font=font)
        draw.text(xy=(25, current_line_height), text=name, fill="black", font=font)
    trimmed = trim(img)
    return trimmed


def _render_map(map_: StaticMap) -> t.Optional[Image.Image]:  # no test coverage
    try:
        img = map_.render()
    except Exception:
        try:
            img = map_.render()
        except Exception:
            log.error("Error rendering map", exc_info=True)
            img = None
    return img


def _merge_maps(
    overview_img: t.Optional[Image.Image],
    detailed_img: t.Optional[Image.Image],
    legend: Image.Image,
) -> t.Optional[bytes]:
    if detailed_img is not None:
        detailed_img.paste(legend, (detailed_img.width - legend.width, 0))

    if overview_img is not None and detailed_img is not None:
        sep = Image.new("RGB", (3, overview_img.height), (255, 255, 255))
        img = Image.new(
            "RGB",
            (
                (overview_img.width + sep.width + detailed_img.width),
                overview_img.height,
            ),
        )
        img.paste(overview_img, (0, 0))
        img.paste(sep, (overview_img.width, 0))
        img.paste(detailed_img, (overview_img.width + sep.width, 0))
    elif overview_img is not None:  # no test coverage
        img = overview_img
    elif detailed_img is not None:  # no test coverage
        img = detailed_img
    else:  # no test coverage
        return None
    bytes_io = BytesIO()
    img.save(bytes_io, format="JPEG", subsampling=0, quality=100)
    return bytes_io.getvalue()


def main(
    db: Database,
    trek_id: Id,
    leg_id: Id,
    date: pendulum.Date,
    last_location: t.Optional[Location],
    current_location: PointT,
    current_distance: float,
    users_progress: list[UserProgress],
    upload_func: UploadFunc,
) -> t.Optional[str]:
    current_lat, current_lon = current_location
    old_points, location_points, leg_points, day_points = _traversal_data(
        db,
        trek_id,
        leg_id,
        last_location,
        current_lat,
        current_lon,
        current_distance,
        users_progress,
    )

    template = "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"
    height = 600
    width = 1000
    overview_map = StaticMap(width=width, height=height, url_template=template)
    if old_points:
        overview_map.add_line(Line(old_points, "grey", 2))
    for lon, lat in location_points:
        overview_map.add_marker(CircleMarker((lon, lat), "blue", 6))
    overview_map.add_line(Line(leg_points, "red", 2))
    overview_map.add_marker(CircleMarker((current_lon, current_lat), "red", 6))

    detailed_map = StaticMap(width=width, height=height, url_template=template)
    start = day_points[0][1][0]
    detailed_map.add_marker(CircleMarker(start, "black", 6))
    detailed_map.add_marker(CircleMarker(start, "grey", 4))
    for user, points in day_points:
        color = user["trek_user"]["color"]
        detailed_map.add_line(Line(points, "grey", 4))
        detailed_map.add_line(Line(points, color, 2))
        detailed_map.add_marker(CircleMarker(points[-1], "black", 6))
        detailed_map.add_marker(CircleMarker(points[-1], color, 4))
    legend = _map_legend(day_points)

    overview_img = _render_map(overview_map)
    detailed_img = _render_map(detailed_map)
    img = _merge_maps(overview_img, detailed_img, legend)
    if img is None:
        return None
    path = upload_func(img, trek_id, leg_id, date, "traversal_map")
    return path
