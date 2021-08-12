from __future__ import annotations

import logging
import sys

from fastapi import FastAPI

from trek import location, logging_conf, route, trek
from trek.database import database

# from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)

app = FastAPI()
app.include_router(location.router)
app.include_router(route.router)
app.include_router(trek.router)
DEBUG_MODE = "--reload" in sys.argv
TESTING = sys.argv[0].endswith("ward/__main__.py")


@app.on_event("startup")
async def startup_event():
    logging.config.dictConfig(logging_conf.LOGGING_CONFIG)  # type: ignore


@app.on_event("startup")
async def startup():
    try:
        await database.connect()
    except ConnectionRefusedError:
        if not DEBUG_MODE:
            raise
        log.warn("No database connection")


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


# @app.exception_handler(StarletteHTTPException)
# async def http_exception_handler(request, exc):
#     print(exc)
#     1 / 0
