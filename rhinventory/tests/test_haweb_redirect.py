import pytest
from flask.testing import FlaskClient

from rhinventory.models.file import File, FileCategory, FileStore, Privacy


EMBED_HEADERS = {
    'X-Forwarded-Prefix': '/inventory/_frame',
    'X-Haweb-Embed': '1',
    'X-Haweb-Theme': 'dark',
}


HAWEB_INVENTORY_URL = "https://herniarchiv.cz/inventory"


@pytest.fixture()
def haweb_redirect(app):
    app.config["HAWEB_INVENTORY_URL"] = HAWEB_INVENTORY_URL


@pytest.mark.parametrize("url", ["/", "/asset/", "/asset/?page=2&sort=1", "/file/"])
def test_anonymous_redirected_to_haweb(anonymous_client: FlaskClient, haweb_redirect, url: str):
    response = anonymous_client.get(url)
    assert response.status_code == 302
    assert response.location == HAWEB_INVENTORY_URL + url
    assert "Cookie" in response.headers["Vary"]


def test_anonymous_staff_page_redirected_to_haweb_with_next(anonymous_client: FlaskClient, haweb_redirect):
    response = anonymous_client.get("/transaction/")
    assert response.status_code == 302
    assert response.location.startswith("/?next=")

    response = anonymous_client.get(response.location)
    assert response.status_code == 302
    assert response.location == HAWEB_INVENTORY_URL + "/?next=/transaction/?"


@pytest.mark.parametrize("url,headers", [
    ("/asset/", EMBED_HEADERS),
    ("/asset/", {"HX-Request": "true"}),
    ("/asset/", {"Sec-Fetch-Dest": "empty"}),
    ("/robots.txt", {}),
    ("/public-stats.json", {}),
    ("/public-search.json", {}),
])
def test_anonymous_not_redirected_to_haweb(anonymous_client: FlaskClient, haweb_redirect, url: str, headers: dict):
    response = anonymous_client.get(url, headers=headers)
    assert response.status_code == 200


def test_anonymous_file_not_redirected_to_haweb(anonymous_client: FlaskClient, haweb_redirect, db_session, tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"photo")
    file = File(filepath="photo.jpg", storage=FileStore.local, category=FileCategory.image,
                privacy=Privacy.public)
    db_session.add(file)
    db_session.commit()
    db_session.refresh(file)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setitem(anonymous_client.application.config["FILE_STORE_LOCATIONS"], "local", str(tmp_path))
        response = anonymous_client.get(f"/files/{file.id}/photo.jpg")
    assert response.status_code == 200
    assert response.data == b"photo"


def test_logged_in_not_redirected_to_haweb(client: FlaskClient, haweb_redirect):
    response = client.get("/asset/")
    assert response.status_code == 200


def test_anonymous_not_redirected_without_haweb_url(anonymous_client: FlaskClient):
    response = anonymous_client.get("/asset/")
    assert response.status_code == 200
