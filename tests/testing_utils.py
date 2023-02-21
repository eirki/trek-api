from pathlib import Path
import tempfile
import typing as t  # noqa
import uuid

from fastapi.testclient import TestClient
from ward import fixture

from trek import server
from trek.database import Database
from trek.models import Id


@fixture()
def get_client():
    app = server.make_app()
    client = TestClient(app)
    return client


class FakeAuth:
    def __init__(self, user_id=1):
        self.user_id = user_id

    def __call__(self):
        return self

    def jwt_required(self):
        pass

    def get_jwt_subject(self):
        return self.user_id

    def create_access_token(self, subject):
        return f"access_token-{subject}"


@fixture
def make_temp_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


class TestDatabase(Database):
    def __init__(self, temp_tables_path: Path):
        super().__init__(save_dir=temp_tables_path, load_dir=temp_tables_path)
        self.serial: int = 0

    def make_id(self) -> Id:  # type: ignore
        uuid_id = uuid.UUID(int=self.serial).hex
        id_ = Id(uuid_id)
        self.serial += 1
        return id_

    @classmethod
    def get_db(cls):
        raise NotImplementedError

    def commit_table(self, table):
        pass

    def commit(self):
        pass


@fixture
def test_db(temp_dir: Path = make_temp_dir):
    return TestDatabase(temp_dir)
