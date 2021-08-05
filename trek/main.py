from __future__ import annotations

import logging

from fastapi import FastAPI

from trek import location, logging_conf, route

app = FastAPI()
app.include_router(location.router)
app.include_router(route.router)


@app.on_event("startup")
async def startup_event():
    logging.config.dictConfig(logging_conf.LOGGING_CONFIG)  # type: ignore
