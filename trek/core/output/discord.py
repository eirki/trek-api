import asyncio
from contextlib import asynccontextmanager
import typing as t  # noqa

import discord
import pyarrow.compute as pc
from pydantic import BaseModel

from trek import config, utils
from trek.core.core_utils import assert_trek_owner
from trek.core.output import output_utils
from trek.core.progress.progress_utils import STRIDE, UserProgress, round_meters
from trek.database import Database
from trek.models import Achievement, DiscordChannel, Id, Location, Trek, User


class UrlResponse(BaseModel):
    url: str


def make_authorization_url(
    db: Database,
    trek_id: Id,
    user_id: Id,
    frontend_redirect_url: str,
    backend_redirect_url: str,
) -> UrlResponse:
    assert_trek_owner(db, trek_id, user_id)
    state_params = {
        "frontend_redirect_url": str(frontend_redirect_url),
        "trek_id": trek_id,
    }
    encoded_params = utils.encode_dict(state_params)
    url = discord.utils.oauth_url(
        client_id=config.discord_client_id,
        redirect_uri=backend_redirect_url,
        # https://discordapi.com/permissions.html#466004404304
        permissions=discord.Permissions(466004404304),
        state=encoded_params,
    )
    return UrlResponse(url=url)


def handle_discord_redirect(db: Database, state, guild_id: int):
    state_params = utils.decode_dict(state)
    trek_id = state_params["trek_id"]
    channel_id = asyncio.run(_make_trek_channel(guild_id))
    channel: DiscordChannel = {
        "trek_id": trek_id,
        "guild_id": guild_id,
        "channel_id": channel_id,
    }
    db.upsert_record(DiscordChannel, channel, pc.field("trek_id") == pc.scalar(trek_id))
    frontend_redirect_url = state_params["frontend_redirect_url"]
    return frontend_redirect_url


async def _make_trek_channel(guild_id: int) -> int:
    async with _get_client() as client:
        guild = await client.fetch_guild(guild_id)
        channel = await guild.create_text_channel("trek")
        return channel.id


@asynccontextmanager
async def _get_client():
    intents = discord.Intents.all()
    client = discord.Client(intents=intents)
    try:
        await client.login(config.discord_bot_token)
        yield client
    finally:
        await client.close()


async def _post_message(
    message: str,
    output_data: DiscordChannel,
    embeds: t.Optional[list[discord.Embed]] = None,
):
    async with _get_client() as client:
        guild = await client.fetch_guild(output_data["guild_id"])
        channel = await guild.fetch_channel(output_data["channel_id"])
        await channel.send(message, embeds=embeds)


class DiscordOutputter(output_utils.Outputter):
    @staticmethod
    def post_leg_reminder(db: Database, trek: Trek, next_adder: User):
        message = _prepare_leg_reminder(trek, next_adder)
        try:
            output_data = db.load_records(
                DiscordChannel, pc.field("trek_id") == pc.scalar(trek["id"])
            )[0]
        except IndexError:
            return
        asyncio.run(_post_message(message, output_data))

    @staticmethod
    def post_update(
        db: Database,
        trek: Trek,
        users_progress: list[UserProgress],
        location: Location,
        achievements: t.Optional[list[Achievement]],
        next_adder: t.Optional[User],
    ):
        blocks = _format_output(
            trek=trek,
            users_progress=users_progress,
            location=location,
            achievements=achievements,
            next_adder=next_adder,
        )

        message = "\n\n".join(blocks).format(
            achievement=":trophy:",
            first_place=":first_place:",
            last_place=":turtle:",
            second_place=":second_place:",
            third_place=":third_place: ",
            new_country=":confetti_ball:",
        )
        try:
            output_data = db.load_records(
                DiscordChannel, pc.field("trek_id") == pc.scalar(trek["id"])
            )[0]
        except IndexError:
            return
        embeds = []
        embeds.append(
            discord.Embed.from_dict(
                {
                    "type": "rich",
                    "url": location["gmap_url"],
                    "title": "GoggleMaps",
                    "image": {"url": location["photo_url"]},
                }
            )
        )
        # if location["traversal_map_url"]:
        embeds.append(
            discord.Embed.from_dict(
                {
                    "type": "rich",
                    "title": "Reisekart",
                    "url": f"{config.frontend_url}/#/trek/{trek['id']}",
                    "image": {"url": location["traversal_map_url"]},
                }
            )
        )

        asyncio.run(_post_message(message, output_data, embeds))


def _format_achivement(
    achievement: Achievement, user_for_user_id: dict[Id, User]
) -> str:
    user = user_for_user_id[achievement["user_id"]]
    old_user = user_for_user_id[achievement["old_user_id"]]
    formatted = (
        f"{user['name']} {{achievement}} har satt ny rekord: {achievement['description']}, med {achievement['amount']} {achievement['unit']}! "
        f"Forrige record holder var {old_user['name']}, med {achievement['old_amount']} {achievement['unit']}. Huzzah!"
    )
    return formatted


def _format_output(
    trek: Trek,
    users_progress: list[UserProgress],
    location: Location,
    achievements: t.Optional[list[Achievement]],
    next_adder: t.Optional[User],
) -> list[str]:
    blocks: list[str] = []
    user_for_user_id = {user["user"]["id"]: user["user"] for user in users_progress}

    date = location["added_at"]
    title_txt = f"**Trek-rapport {date.day}.{date.month}.{date.year}**"
    blocks.append(title_txt)

    steps_txt = "Steg:"
    most_steps = users_progress[0]["step"]["amount"]
    fewest_steps = users_progress[-1]["step"]["amount"]
    for i, row in enumerate(users_progress):

        steps = row["step"]["amount"]
        name = row["user"]["name"]
        user_distance = round_meters(steps * STRIDE)
        if steps == most_steps:
            amount = f"{steps} ({user_distance}) {{first_place}}"
        elif steps == fewest_steps:
            amount = f"_{steps}_ ({user_distance}) {{last_place}}"
        elif i == 1:
            amount = f"{steps} ({user_distance}) {{second_place}}"
        elif i == 2:
            amount = f"{steps} ({user_distance}) {{third_place}}"
        else:
            amount = f"{steps} ({user_distance})"
        desc = f"\n\t- {name}: {amount}"
        steps_txt += desc
    blocks.append(steps_txt)

    if achievements:
        for achievement in achievements:
            achievement_formatted = _format_achivement(achievement, user_for_user_id)
            blocks.append(achievement_formatted)

    if location["factoid"] is not None:
        blocks.append(location["factoid"])

    location_txt = ""
    if location["country"] is not None and location["is_new_country"]:
        location_txt += f"Velkommen til {location['country']}! {{new_country}} "
    if location["address"] is not None:
        location_txt += f"Vi har nå kommet til {location['address']}. "
    if location["poi"] is not None:
        location_txt += f"Dagens underholdning er {location['poi']}."
    if location_txt:
        blocks.append(location_txt)

    if location["is_last_in_leg"] and next_adder is not None:
        adder_name = (
            next_adder["name"].capitalize()
            if next_adder["name"] is not None
            else next_adder["id"]
        )
        reminder = (
            "Etappen er nå ferdig! "
            f"{adder_name} må gå inn på {config.frontend_url}/#/{trek['id']} og legge til ny etappe."
        )
        blocks.append(reminder)
    return blocks


def _prepare_leg_reminder(trek: Trek, next_adder: User) -> str:
    adder_name = (
        next_adder["name"].capitalize()
        if next_adder["name"] is not None
        else next_adder["id"]
    )
    reminder = (
        "Vi trenger en ny etappe! "
        f"{adder_name} må gå inn på {config.frontend_url}/#/{trek['id']} og legge til ny etappe."
    )
    return reminder
