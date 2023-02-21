from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from fastapi_jwt_auth import AuthJWT

from trek.core import user
from trek.core.trackers import trackers
from trek.database import Database
from trek.models import TrackerName

router = APIRouter(prefix="/user", tags=["users"])


@router.get("/login/{tracker_name}")
def login(
    tracker_name: TrackerName, frontend_redirect_url: str
) -> user.AuthorizeResponse:
    Service = trackers.name_to_service[tracker_name]
    service = Service()
    return user.authorize(service, frontend_redirect_url)


@router.get("/add_tracker/{tracker_name}", operation_id="authorize")
def add_tracker(
    tracker_name: TrackerName,
    frontend_redirect_url: str,
    Authorize: AuthJWT = Depends(),
) -> user.AuthorizeResponse:
    Authorize.jwt_required()
    user_id = Authorize.get_jwt_subject()
    Service = trackers.name_to_service[tracker_name]
    service = Service()
    return user.add_tracker(service, frontend_redirect_url, user_id)


@router.get("/redirect/{tracker_name}", include_in_schema=False)
def handle_redirect(
    tracker_name: TrackerName,
    code: str,
    state: str,
    db: Database = Depends(Database.get_db),
    Authorize: AuthJWT = Depends(),
):
    Service = trackers.name_to_service[tracker_name]
    service = Service()
    return RedirectResponse(
        user.handle_redirect(
            service=service,
            code=code,
            state=state,
            db=db,
            Authorize=Authorize,
        )
    )


@router.get("/me", operation_id="authorize")
def me(
    db: Database = Depends(Database.get_db), Authorize: AuthJWT = Depends()
) -> user.MeResponse:
    Authorize.jwt_required()
    user_id = Authorize.get_jwt_subject()
    return user.me(db, user_id)


@router.get(
    "/is_authenticated",
    operation_id="authorize",
)
def is_authenticated(
    db: Database = Depends(Database.get_db), Authorize: AuthJWT = Depends()
) -> user.IsAuthenticatedResponse:
    Authorize.jwt_required()
    user_id = Authorize.get_jwt_subject()
    return user.is_authenticated(db, user_id)


@router.put("/me", operation_id="authorize")
def edit_user(
    request: user.EditUserRequest,
    db: Database = Depends(Database.get_db),
    Authorize: AuthJWT = Depends(),
) -> None:
    Authorize.jwt_required()
    user_id = Authorize.get_jwt_subject()
    return user.edit_user(request, db, user_id)
