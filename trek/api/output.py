import logging
import typing as t  # noqa

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from fastapi_jwt_auth import AuthJWT

from trek import config
from trek.core.output import discord
from trek.database import Database
from trek.models import Id
from trek.utils import protect_endpoint

log = logging.getLogger(__name__)
router = APIRouter(prefix="/output", tags=["output"])

HANDLE_REDIRECT_ENDPOINT_NAME = "handle_discord_redirect"


@router.post(
    "/discord/add/{trek_id}",
    dependencies=[Depends(protect_endpoint)],
    operation_id="authorize",
)
def make_discord_add_url(
    trek_id: Id,
    frontend_redirect_url: str,
    db: Database = Depends(Database.get_db),
    Authorize: AuthJWT = Depends(),
) -> discord.UrlResponse:
    user_id = Authorize.get_jwt_subject()
    backend_redirect_url = config.backend_url + router.url_path_for(
        HANDLE_REDIRECT_ENDPOINT_NAME
    )
    return discord.make_authorization_url(
        db=db,
        trek_id=trek_id,
        user_id=user_id,
        frontend_redirect_url=frontend_redirect_url,
        backend_redirect_url=backend_redirect_url,
    )


@router.get(
    "/discord/redirect", name=HANDLE_REDIRECT_ENDPOINT_NAME, include_in_schema=False
)
def handle_discord_redirect(
    state: str,
    guild_id: int,
    code: str,
    permissions: int,
    db: Database = Depends(Database.get_db),
):
    frontend_redirect_url = discord.handle_discord_redirect(db, state, guild_id)
    return RedirectResponse(frontend_redirect_url)
