from fastapi import APIRouter, Depends
from fastapi_jwt_auth import AuthJWT

from trek.core import crud
from trek.database import Database
from trek.models import Id
from trek.utils import protect_endpoint

router = APIRouter(
    prefix="/trek", tags=["treks"], dependencies=[Depends(protect_endpoint)]
)


@router.post("", operation_id="authorize")
def add_trek(
    request: crud.AddTrekRequest,
    db: Database = Depends(Database.get_db),
    Authorize: AuthJWT = Depends(),
) -> crud.AddTrekResponse:
    user_id = Authorize.get_jwt_subject()
    return crud.add_trek(request, db, user_id)


@router.get("/{trek_id}", operation_id="authorize")
def get_trek(
    trek_id: Id,
    db: Database = Depends(Database.get_db),
    Authorize: AuthJWT = Depends(),
) -> crud.GetTrekResponse:
    user_id = Authorize.get_jwt_subject()
    return crud.get_trek(trek_id=trek_id, db=db, user_id=user_id)


@router.put("/{trek_id}", operation_id="authorize")
def edit_trek(
    trek_id: Id,
    request: crud.EditTrekRequest,
    db: Database = Depends(Database.get_db),
    Authorize: AuthJWT = Depends(),
) -> None:
    user_id = Authorize.get_jwt_subject()
    return crud.edit_trek(trek_id=trek_id, request=request, db=db, user_id=user_id)


@router.delete("/{trek_id}", operation_id="authorize")
def delete_trek(
    trek_id: Id,
    db: Database = Depends(Database.get_db),
    Authorize: AuthJWT = Depends(),
):
    user_id = Authorize.get_jwt_subject()
    return crud.delete_trek(trek_id=trek_id, db=db, user_id=user_id)


@router.get("/{trek_id}/invitation", operation_id="authorize")
def generate_trek_invite(
    trek_id: Id,
    db: Database = Depends(Database.get_db),
    Authorize: AuthJWT = Depends(),
) -> crud.GenerateInviteResponse:
    user_id = Authorize.get_jwt_subject()
    return crud.generate_trek_invite(trek_id=trek_id, user_id=user_id, db=db)


@router.post("/{encrypted_trek_id}/join", operation_id="authorize")
def join_trek(
    encrypted_trek_id: str,
    db: Database = Depends(Database.get_db),
    Authorize: AuthJWT = Depends(),
) -> crud.JoinTrekResponse:
    user_id = Authorize.get_jwt_subject()
    return crud.add_user_to_trek(
        encrypted_trek_id=encrypted_trek_id, db=db, user_id=user_id
    )


@router.post("/{trek_id}/leg", operation_id="authorize")
def add_leg(
    trek_id: Id,
    request: crud.AddLegRequest,
    db: Database = Depends(Database.get_db),
    Authorize: AuthJWT = Depends(),
) -> crud.AddLegResponse:
    user_id = Authorize.get_jwt_subject()
    return crud.add_leg(trek_id=trek_id, request=request, db=db, user_id=user_id)


@router.get("/{trek_id}/leg/{leg_id}", operation_id="authorize")
def get_leg(
    trek_id: Id,
    leg_id: Id,
    db: Database = Depends(Database.get_db),
    Authorize: AuthJWT = Depends(),
) -> crud.GetLegResponse:
    user_id = Authorize.get_jwt_subject()
    return crud.get_leg(trek_id=trek_id, leg_id=leg_id, db=db, user_id=user_id)
