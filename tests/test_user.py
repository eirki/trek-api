from ward import test

from tests import conftest
from tests.conftest import all_rows_in_table, client, connect_db
from trek import trackers, user


@test("test_add_user ")
async def test_add_user(db=connect_db):
    user_id = await user.add_user(db)
    assert user_id == 1
    res = await all_rows_in_table(db, "user_")
    exp = [{"id": 1, "is_admin": False}]
    assert res == exp


class FakeService:
    auth_url = "https://authorization.url"

    def authorization_url(self) -> str:
        return self.auth_url

    def token(self, code: str) -> dict:
        pass

    def tracker_user_id_from_token(self, token: dict) -> str:
        pass

    @property
    def User(self):
        return FakeUser


class FakeUser:
    def __init__(self, *args, **kwargs):
        pass

    async def persist_token(self, token: dict):
        pass


@test("test_auth ")
async def test_auth(
    _=conftest.overide({"fitbit": FakeService}, container=trackers.name_to_service),
):
    response = await client.get(
        "/user/auth/fitbit", query_string={"redirect_url": "https://www.redirect.me"}
    )
    res = response.json()
    assert "auth_url" in res
    assert res["auth_url"].startswith(FakeService.auth_url)


@test("test_redirect ")
async def test_redirect(
    _a=connect_db,
    _b=conftest.overide({"fitbit": FakeService}, container=trackers.name_to_service),
):
    response = await client.get(
        "/user/redirect/fitbit",
        query_string={
            "state": "eyJyZWRpcmVjdF91cmwiOiAiaHR0cHM6Ly93d3cucmVkaXJlY3QubWUifQ==",
            "code": "thisisacode",
        },
        allow_redirects=False,
    )
    assert response.status_code == 307  # redirect
    assert response.headers["location"].startswith("https://www.redirect.me")


@test("is_authenticated")
async def test_is_authenticated(_=conftest.overide(conftest.auth_overrides(user_id=4))):
    response = await client.get("/user/is_authenticated")
    assert response.status_code == 200
    res = response.json()
    exp = {"user_id": 4}
    assert res == exp


@test("not_is_authenticated")
async def test_not_is_authenticated():
    response = await client.get("/user/is_authenticated")
    assert response.status_code == 401
