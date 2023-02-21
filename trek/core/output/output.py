import typing as t  # noqa

from trek.core.output import discord, output_utils
from trek.models import OutputName

outputters: dict[OutputName, output_utils.Outputter] = {
    "discord": discord.DiscordOutputter(),
    # "telegram": telegram,
}
