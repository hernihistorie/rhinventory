from flask.testing import FlaskClient


def test_index(client: FlaskClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "O naší sbírce" in response.data.decode('utf-8')
