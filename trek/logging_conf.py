# https://github.com/br3ndonland/inboard/blob/develop/inboard/logging_conf.py
# https://github.com/tiangolo/fastapi/issues/1508
import os

LOG_LEVEL = str(os.getenv("LOG_LEVEL", "info")).upper()
LOGGING_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default_formatter": {
            "class": "uvicorn.logging.ColourizedFormatter",
            "format": "{levelprefix:<8} {name:<15} {message}",
            "use_colors": True,
            "style": "{",
        },
    },
    "handlers": {
        "default_handler": {
            "class": "logging.StreamHandler",
            "formatter": "default_formatter",
            "level": LOG_LEVEL,
            "stream": "ext://sys.stdout",
        }
    },
    "root": {
        "handlers": ["default_handler"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "fastapi": {"propagate": True},
        "uvicorn": {"propagate": True},
        "uvicorn.access": {"propagate": True},
        "uvicorn.asgi": {"propagate": True},
        "uvicorn.error": {"propagate": True},
    },
}
