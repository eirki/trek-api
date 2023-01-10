from io import BytesIO
import logging
import typing as t

from PIL import Image, ImageChops, ImageDraw, ImageFont
from asyncpg import Connection
from colorhash import ColorHash
import pendulum
from staticmap import CircleMarker, Line, StaticMap

from trek.progress import progress_utils
from trek.progress.progress_utils import Uploader, queries

log = logging.getLogger(__name__)


def _get_detailed_coords(current_waypoints, last_location, steps_data, start_dist):
    detailed_coords: list[dict] = []
    waypoints_itr = iter(current_waypoints)
    # starting location
    latest_waypoint = (
        last_location if last_location is not None else current_waypoints[0]
    )
    current_distance = start_dist
    next_waypoint = None
    for user in steps_data:
        user_coords = []
        user_coords.append(
            (
                latest_waypoint["lon"],
                latest_waypoint["lat"],
            )
        )
        user_distance = user["amount"] * progress_utils.STRIDE
        current_distance += user_distance
        while True:
            if next_waypoint is None or next_waypoint["distance"] < current_distance:
                # next_waypoint from previous users has been passed
                next_waypoint = next(waypoints_itr, None)
                assert next_waypoint is not None

            if next_waypoint["distance"] < current_distance:
                # next_waypoint passed by this user
                user_coords.append((next_waypoint["lon"], next_waypoint["lat"]))
                latest_waypoint = next_waypoint
                continue
            elif next_waypoint["distance"] >= current_distance:
                # next_waypoint will not be passed by this user
                remaining_dist = current_distance - latest_waypoint["distance"]
                last_lat, last_lon = progress_utils.location_between_waypoints(
                    latest_waypoint, next_waypoint, remaining_dist
                )
                user_coords.append((last_lon, last_lat))
                # assign starting location for next user
                latest_waypoint = {
                    "lat": last_lat,
                    "lon": last_lon,
                    "distance": current_distance,
                }
                break
        detailed_coords.append({"user_id": user["user_id"], "coords": user_coords})
    return detailed_coords


def _traversal_data(
    db: Connection,
    trek_id: int,
    leg_id: int,
    last_location: t.Optional[dict],
    current_lat: float,
    current_lon: float,
    current_distance: float,
    steps_data: list[dict],
) -> tuple[
    list[tuple[float, float]],
    list[tuple[float, float]],
    list[tuple[float, float]],
    list[dict],
]:
    if last_location is not None:
        old_waypoints = (
            queries.waypoints_between_distances(  # FIXME query does not exist
                db,
                trek_id=trek_id,
                leg_id=leg_id,
                low=0,
                high=last_location["distance"],
            )
        )
        old_coords = [(loc["lon"], loc["lat"]) for loc in old_waypoints]
        old_coords.append((last_location["lon"], last_location["lat"]))
        locations = queries.location_between_distances(  # FIXME query does not exist
            db, trek_id=trek_id, leg_id=leg_id, low=0, high=last_location["distance"]
        )
        location_coordinates = [(old_waypoints[0]["lon"], old_waypoints[0]["lat"])]
        location_coordinates.extend([(loc["lon"], loc["lat"]) for loc in locations])
        start_dist = last_location["distance"]
        overview_coords = [(last_location["lon"], last_location["lat"])]
    else:
        old_coords = []
        location_coordinates = []
        start_dist = 0
        overview_coords = []

    current_waypoints = (
        queries.waypoints_between_distances(  # FIXME query does not exist
            db, trek_id=trek_id, leg_id=leg_id, low=start_dist, high=current_distance
        )
    )
    current_waypoints.append(
        {"lat": current_lat, "lon": current_lon, "distance": current_distance}
    )
    overview_coords.extend([(loc["lon"], loc["lat"]) for loc in current_waypoints])
    overview_coords.append((current_lon, current_lat))

    detailed_coords = _get_detailed_coords(
        current_waypoints, last_location, steps_data, start_dist
    )
    return old_coords, location_coordinates, overview_coords, detailed_coords


def _map_legend(user_coords: list[dict], user_info) -> Image.Image:
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
    for i, user in enumerate(user_coords):
        current_line_height = (line_height + padding) * (i + 1)
        color = user_info[user["user_id"]]["color_hex"]
        name = user_info[user["user_id"]]["first_name"]
        draw.text(
            xy=(0, current_line_height),
            text="—",
            fill=color,
            font=font,
        )
        draw.text(
            xy=(25, current_line_height),
            text=name,
            fill="black",
            font=font,
        )
    trimmed = trim(img)
    return trimmed


def _render_map(
    map_: StaticMap, retry=True
) -> t.Optional[Image.Image]:  # no test coverage
    try:
        img = map_.render()
    except Exception:
        if retry:
            return _render_map(map_, retry=False)
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


async def main(
    db: Connection,
    trek_id: int,
    leg_id: int,
    date: pendulum.Date,
    last_location: t.Optional[dict],
    current_location: tuple[float, float],
    current_distance: float,
    steps_data,
    user_info,
    uploader: Uploader,
) -> t.Optional[str]:
    current_lat, current_lon = current_location
    old_coords, locations, overview_coords, detailed_coords = _traversal_data(
        db,
        trek_id,
        leg_id,
        last_location,
        current_lat,
        current_lon,
        current_distance,
        steps_data,
    )
    template = "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"
    height = 600
    width = 1000
    overview_map = StaticMap(width=width, height=height, url_template=template)
    if old_coords:
        overview_map.add_line(Line(old_coords, "grey", 2))
    for lon, lat in locations:
        overview_map.add_marker(CircleMarker((lon, lat), "blue", 6))
    overview_map.add_line(Line(overview_coords, "red", 2))
    overview_map.add_marker(CircleMarker((current_lon, current_lat), "red", 6))

    detailed_map = StaticMap(width=width, height=height, url_template=template)
    start = detailed_coords[0]["coords"][0]
    detailed_map.add_marker(CircleMarker(start, "black", 6))
    detailed_map.add_marker(CircleMarker(start, "grey", 4))
    for user in detailed_coords:
        color = user_info[user["user_id"]]["color_hex"]
        detailed_map.add_line(Line(user["coords"], "grey", 4))
        detailed_map.add_line(Line(user["coords"], color, 2))
        detailed_map.add_marker(CircleMarker(user["coords"][-1], "black", 6))
        detailed_map.add_marker(CircleMarker(user["coords"][-1], color, 4))
    legend = _map_legend(detailed_coords, user_info)

    overview_img = _render_map(overview_map)
    detailed_img = _render_map(detailed_map)
    img = _merge_maps(overview_img, detailed_img, legend)
    if img is None:
        return None
    path = await uploader(img, trek_id, leg_id, date, "traversal_map")
    return path
