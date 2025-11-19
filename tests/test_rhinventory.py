"""
Tests for rhinventory application.

These tests use PostgreSQL running in a podman container.
The conftest.py file manages the container lifecycle and database setup.
"""
from flask.testing import FlaskClient

from rhinventory.models.asset import AssetCategory


def test_index(client: FlaskClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "O naší sbírce" in response.data.decode('utf-8')


def test_asset_list(client: FlaskClient):
    response = client.get("/asset/")
    assert response.status_code == 200


def test_asset_new(client: FlaskClient):
    url = "/asset/new/"
    asset_name = "Test Object 123"

    client.get(url)
    response = client.post(url, data={
        "organization": "1",
        "category": AssetCategory.game.name,
        "name": asset_name,
    }, follow_redirects=False)
    assert response.status_code in (302, 200)

    response = client.get("/asset/")
    assert response.status_code == 200
    assert asset_name in response.data.decode('utf-8')

    response = client.get("/asset/details/?id=1")
    assert response.status_code == 200
    assert asset_name in response.data.decode('utf-8')

    response = client.get("/asset/edit/?id=1")
    assert response.status_code == 200
    assert asset_name in response.data.decode('utf-8')


def test_transaction_list(client: FlaskClient):
    response = client.get("/transaction/")
    assert response.status_code == 200


def test_file_list(client: FlaskClient):
    response = client.get("/file/")
    assert response.status_code == 200


def test_file_upload(client: FlaskClient):
    response = client.get("/file/upload/")
    assert response.status_code == 200
