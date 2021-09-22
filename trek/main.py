from __future__ import annotations

import logging
import sys

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException
from pydantic import BaseModel

from trek import config, crud, database, frontend, logging_conf, search, user

log = logging.getLogger(__name__)

app = FastAPI()
app.include_router(search.router)
app.include_router(crud.router)
app.include_router(user.router)
app.include_router(frontend.router)

DEBUG_MODE = "--reload" in sys.argv
TESTING = sys.argv[0].endswith("ward/__main__.py")


class AuthSettings(BaseModel):
    authjwt_secret_key: str = config.jwt_secret_key


@AuthJWT.load_config
def get_auth_config():
    return AuthSettings()


@app.on_event("startup")
async def startup_event():
    logging.config.dictConfig(logging_conf.LOGGING_CONFIG)  # type: ignore


@app.on_event("startup")
async def startup():
    try:
        await database.database_pool.connect()
    except Exception:
        if not DEBUG_MODE:
            raise
        log.warn("No database connection")
    else:
        async with database.database_pool.transaction():
            await database.register_json_conversion(
                database.database_pool.connection().raw_connection
            )


@app.on_event("shutdown")
async def shutdown():
    await database.database_pool.disconnect()


@app.exception_handler(AuthJWTException)
def authjwt_exception_handler(request: Request, exc: AuthJWTException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Trek",
        version="0",
        description="trek",
        routes=app.routes,
    )

    # Custom documentation fastapi-jwt-auth
    headers = {
        "name": "Authorization",
        "in": "header",
        "required": True,
        "schema": {"title": "Authorization", "type": "string"},
    }

    # Get routes from index 4 because before that fastapi define router for /openapi.json, /redoc, /docs, etc
    # Get all router where operation_id is authorize
    router_authorize = [
        route for route in app.routes[4:] if route.operation_id == "authorize"  # type: ignore
    ]

    for route in router_authorize:
        method = list(route.methods)[0].lower()  # type: ignore
        try:
            # If the router has another parameter
            openapi_schema["paths"][route.path][method]["parameters"].append(  # type: ignore
                headers
            )
        except Exception:
            # If the router doesn't have a parameter
            openapi_schema["paths"][route.path][method].update(  # type: ignore
                {"parameters": [headers]}
            )

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore
