from __future__ import annotations

from contextlib import suppress
import logging
import sys

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException
from pydantic import BaseModel

from trek import config, crud, database, logging_conf, search, user

log = logging.getLogger(__name__)
origins = [
    "https://www.bogsynth.com",
    "https://bogsynth.com",
    "http://localhost",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]


app = FastAPI()
app.include_router(search.router)
app.include_router(crud.router)
app.include_router(user.router)
app.mount("/", StaticFiles(directory="frontend"), name="frontend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEBUG_MODE = "--reload" in sys.argv
TESTING = sys.argv[0].endswith("ward/__main__.py")


class AuthSettings(BaseModel):
    authjwt_secret_key: str = config.jwt_secret_key
    authjwt_access_token_expires = False


@AuthJWT.load_config
def get_auth_config():
    return AuthSettings()


@app.on_event("startup")
async def startup_event():  # pragma: no cover
    logging.config.dictConfig(logging_conf.LOGGING_CONFIG)  # type: ignore


@app.on_event("startup")
async def startup():  # pragma: no cover
    try:
        await database.get_pool()
    except Exception:
        if not DEBUG_MODE:
            raise
        log.warn("No database connection")


@app.on_event("shutdown")
async def shutdown():
    pool = await database.get_pool()
    await pool.close()


@app.exception_handler(AuthJWTException)
def authjwt_exception_handler(request: Request, exc: AuthJWTException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def custom_openapi():  # pragma: no cover
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
    router_authorize = []
    for route in app.routes[4:]:
        with suppress(AttributeError):
            if route.operation_id == "authorize":  # type: ignore
                router_authorize.append(route)
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

if True:
    from asyncpg import Connection
    from fastapi import Depends

    from trek.database import get_db


@app.get("/health")
async def health(db: Connection = Depends(get_db)):
    # res = await db.fetch_one("select true;")
    res = await db.fetch("SELECT 1")
    return {
        "db": res,
        "status": "ok",
    }
