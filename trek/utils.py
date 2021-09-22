from __future__ import annotations

import typing as t

from fastapi import Depends, HTTPException
from fastapi_jwt_auth import AuthJWT


def raise_http_exc(
    error: Exception | None,
    data: dict = None,
    message="UnknownError",
) -> t.NoReturn:
    detail = {"message": message}
    if data is not None:
        detail = detail | data
    if error:
        raise HTTPException(status_code=400, detail=detail) from error
    else:
        raise HTTPException(status_code=400, detail=detail)


def protect_endpoint(Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()
