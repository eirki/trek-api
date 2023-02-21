from ward import test

from tests.testing_utils import get_client


@test("test_health")
def test_health(client=get_client):
    response = client.get("/health")
    assert response.status_code == 200, response.text
