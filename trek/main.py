from __future__ import annotations

import logging
import sys

from fastapi import FastAPI

from trek import crud, database, logging_conf, search, user

log = logging.getLogger(__name__)

app = FastAPI()
app.include_router(search.router)
app.include_router(crud.router)
app.include_router(user.router)
DEBUG_MODE = "--reload" in sys.argv
TESTING = sys.argv[0].endswith("ward/__main__.py")


@app.on_event("startup")
async def startup_event():
    logging.config.dictConfig(logging_conf.LOGGING_CONFIG)  # type: ignore


@app.on_event("startup")
async def startup():
    try:
        await database.connect()
    except Exception:
        if not DEBUG_MODE:
            raise
        log.warn("No database connection")


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()
