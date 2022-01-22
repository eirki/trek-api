from databases import Database
from ward import test

from tests import conftest
from tests.conftest import all_rows_in_table, client, connect_db
from trek import trackers, user


class FakeService:
    auth_url = "https://authorization.url"
    _tracker_user_id = None

    def authorization_url(self) -> str:
        return self.auth_url

    def token(self, code: str) -> dict:
        pass

    def tracker_user_id_from_token(self, token: dict):
        return self._tracker_user_id

    @property
    def User(self):
        return FakeUser


class FakeUser:
    def __init__(self, *args, **kwargs):
        pass

    async def persist_token(self, token: dict):
        pass


async def _preadd_users(db: Database) -> list[int]:
    sql = """insert into
            user_ (is_admin)
        values
            (:is_admin);
        """
    await db.execute_many(sql, values=[{"is_admin": False}] * 3)
    user_ids = await db.fetch_all("select id from user_")
    assert len(user_ids) > 0
    as_int = [user["id"] for user in user_ids]
    assert all(isinstance(user_id, int) for user_id in as_int)
    return as_int


@test("test_add_user ")
async def test_add_user(db=connect_db):
    user_id = await user.add_user(db)
    assert user_id == 1
    res = await all_rows_in_table(db, "user_")
    exp = [{"id": 1, "is_admin": False}]
    assert res == exp


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


@test("test_redirect_new_user ")
async def test_redirect_new_user(
    db=connect_db,
    _=conftest.overide({"fitbit": FakeService}, container=trackers.name_to_service),
):
    user_ids = await _preadd_users(db)
    user_id = user_ids[0]
    tracker_user_id = "my_tracker_user_id"
    fake_service = trackers.name_to_service["fitbit"]
    fake_service._tracker_user_id = tracker_user_id  # type: ignore
    await trackers._tracker_utils.queries.persist_token(
        db,
        token="my_token",
        user_id_=user_id,
        tracker="fitbit",
        tracker_user_id=tracker_user_id,
    )
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


@test("test_redirect_new_login_existing_user ")
async def test_redirect_new_login_existing_user(
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
