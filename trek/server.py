from contextlib import suppress
import logging
import traceback

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException
from pydantic import BaseModel

from trek import config
from trek import exceptions as exc
from trek import logging_conf
from trek.api import crud, output, search, user

log = logging.getLogger(__name__)
origins = [
    "https://www.bogsynth.com",
    "https://bogsynth.com",
    "http://localhost",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

router = APIRouter()


class AuthSettings(BaseModel):
    authjwt_secret_key: str = config.jwt_secret_key
    authjwt_access_token_expires = False


@AuthJWT.load_config
def get_auth_config():
    return AuthSettings()


def on_startup():  # pragma: no cover
    logging.config.dictConfig(logging_conf.LOGGING_CONFIG)  # type: ignore


def on_shutdown():
    pass


def _exception_data(model: exc.ServerExceptionModel, tracebk: str):
    return {
        "error": {
            "type": model.__class__.__name__,
            "code": str(model.error_code),
            "stack": tracebk,
            "data": model.json(),
        }
    }


def setup_exception_handlers(app):
    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, e: exc.ServerException
    ):  # pragma: no cover
        model = exc.E901UnexpectedError(traceback=traceback.format_exc())
        log.error(
            f"Unexpected error: {type(e).__name__}",
            extra=_exception_data(model, tracebk=traceback.format_exc()),
        )
        return JSONResponse(
            status_code=500,
            content=model.dict(),
        )

    @app.exception_handler(exc.ServerException)
    async def server_exception_handler(request: Request, e: exc.ServerException):
        log.error(
            f"Server error: {e.model.__class__.__name__}",
            extra=_exception_data(e.model, tracebk=traceback.format_exc()),
        )
        return JSONResponse(
            status_code=400,
            content=e.model.dict(),
        )

    @app.exception_handler(AuthJWTException)
    def authjwt_exception_handler(request: Request, exc: AuthJWTException):
        return JSONResponse(
            status_code=exc.status_code, content={"detail": exc.message}
        )


def custom_openapi():  # pragma: no cover
    app = make_app()
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


@router.get("/health")
async def health():
    return {"status": "ok"}


def make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.include_router(search.router)
    app.include_router(crud.router)
    app.include_router(user.router)
    app.include_router(output.router)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_event_handler(event_type="startup", func=on_startup)
    app.add_event_handler(event_type="shutdown", func=on_shutdown)
    setup_exception_handlers(app)

    app.openapi = custom_openapi  # type: ignore

    logging.getLogger().setLevel(logging.DEBUG)

    return app
