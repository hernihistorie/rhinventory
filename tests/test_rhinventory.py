"""
Tests for rhinventory application.

These tests use PostgreSQL running in a podman container.
The conftest.py file manages the container lifecycle and database setup.
"""
import datetime
import io
import os
import re
import shutil
import zipfile

import pytest
from flask.testing import FlaskClient

from rhinventory.extensions import github
from rhinventory.files.hh_code import parse_asset_lookup

from rhinventory.models.asset import Asset, AssetCategory
from rhinventory.models.asset_attributes import AssetTag, Company
from rhinventory.models.enums import Privacy as AssetPrivacy
from rhinventory.models.magdb import Magazine, MagazineIssue, MagazineIssueVersion, \
    MagazineIssueVersionFiles, MagDBFileType
from rhinventory.models.file import (
    BackgroundColor,
    File,
    FileCategory,
    FileStore,
    FileStoreNotConfigured,
    Privacy,
)
from rhinventory.util import safe_next_path


def test_index(client: FlaskClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "O naší sbírce" in response.data.decode('utf-8')


EMBED_HEADERS = {
    'X-Forwarded-Prefix': '/inventory/_frame',
    'X-Haweb-Embed': '1',
    'X-Haweb-Theme': 'dark',
}


# Root-relative URL in an attribute that doesn't start with the embed prefix
UNPREFIXED_URL = re.compile(r'(?:href|src|action)="/(?!/|inventory/_frame/)[^"]*"')


@pytest.mark.parametrize("url", ["/", "/asset/", "/file/", "/transaction/"])
def test_embedded(client: FlaskClient, url: str):
    response = client.get(url, headers=EMBED_HEADERS)
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert 'class="ha-header"' not in html
    assert 'src="/inventory/_frame/static/embed.js" data-theme="dark"' in html
    assert UNPREFIXED_URL.findall(html) == []


def test_embedded_does_not_leak(client: FlaskClient):
    client.get("/asset/", headers=EMBED_HEADERS)

    response = client.get("/asset/")
    html = response.data.decode('utf-8')
    assert '/inventory/_frame' not in html
    assert 'embed.js' not in html
    assert 'class="ha-header"' in html
    assert 'X-Haweb-Embed' in response.headers['Vary']


@pytest.mark.parametrize("filename, asset_id", [
    ("hh10461.jpg", 10461),
    ("hh10480.jpg", 10480),
    ("hh10509.jpg", 10509),
])
def test_read_rh_barcode(app, zbar, test_photos_dir, filename, asset_id):
    app.config['FILE_STORE_LOCATIONS'] = {"local": str(test_photos_dir)}

    with app.app_context():
        file = File(
            filepath=filename,
            storage=FileStore.local,
            category=FileCategory.image,
        )
        assert file.read_rh_barcode() == asset_id


@pytest.mark.parametrize("term, asset_id", [
    ("1234", 1234),
    ("01234", 1234),
    (" hh1234 ", 1234),
    ("HH01234", 1234),
    ("rh-1234", 1234),
    ("hh 1234", 1234),
    ("0", None),
    ("hh", None),
    ("", None),
    ("1234a", None),
    ("hh1234 front", None),
    ("rhythm", None),
])
def test_parse_asset_lookup(term, asset_id):
    assert parse_asset_lookup(term) == asset_id


def test_public_stats(client: FlaskClient, db_session):
    db_session.add_all([
        Asset(organization_id=1, category=AssetCategory.game, name="Private Asset"),
        # Made public before made_public_at existed, must not win over the newer one
        Asset(organization_id=1, category=AssetCategory.game, name="Old Public Asset",
              _privacy=AssetPrivacy.public),
        Asset(organization_id=1, category=AssetCategory.game, name="New Public Asset",
              _privacy=AssetPrivacy.public, made_public_at=datetime.datetime(2026, 1, 1)),
    ])
    db_session.commit()

    response = client.get("/public-stats.json")
    assert response.status_code == 200
    assert response.json["asset_count"] == 3
    latest = response.json["latest_public_asset"]
    assert latest["name"] == "New Public Asset"
    assert latest["slug"] == "new-public-asset"


def test_public_search(anonymous_client: FlaskClient, db_session):
    public_tag = AssetTag(name="Public Tag", description="Tag description", is_collection=True)
    hidden_tag = AssetTag(name="Hidden Tag")
    public_asset = Asset(
        organization_id=1, category=AssetCategory.computer, custom_code=12, name="Public Asset",
        description="Some **bold** text", note="A note", product_codes=["ABC-1"], serial="123",
        _privacy=AssetPrivacy.public, tags=[public_tag], companies=[Company(name="Tesla")],
    )
    db_session.add_all([
        public_asset,
        Asset(organization_id=1, category=AssetCategory.game, name="Private Asset",
              _privacy=AssetPrivacy.private, tags=[public_tag, hidden_tag]),
        Asset(organization_id=1, category=AssetCategory.game, name="Implicitly Private Asset",
              tags=[hidden_tag]),
        Asset(organization_id=1, category=AssetCategory.game, name="Unlinked Asset",
              _privacy=AssetPrivacy.unlinked, tags=[hidden_tag]),
    ])
    db_session.commit()

    response = anonymous_client.get("/public-search.json")
    assert response.status_code == 200
    assert [asset["name"] for asset in response.json["assets"]] == ["Public Asset"]
    asset = response.json["assets"][0]
    assert asset["id"] == public_asset.id
    assert asset["slug"] == "public-asset"
    assert asset["code"] == "PC12"
    assert asset["product_codes"] == ["ABC-1"]
    assert asset["description"] == "Some bold text"
    assert asset["note"] == "A note"
    assert asset["tags"] == ["Public Tag"]
    assert asset["companies"] == ["Tesla"]
    assert asset["image"] is None

    assert [tag["name"] for tag in response.json["tags"]] == ["Public Tag"]
    tag = response.json["tags"][0]
    assert tag["description"] == "Tag description"
    assert tag["is_collection"] is True
    assert tag["list_path"] == "/asset/?flt1_45=Public+Tag"


def test_public_search_images(anonymous_client: FlaskClient, db_session):
    def add_asset(name: str, *files: File) -> None:
        db_session.add(Asset(organization_id=1, category=AssetCategory.game, name=name,
                             _privacy=AssetPrivacy.public, files=list(files)))

    def image(filepath: str, **kwargs) -> File:
        return File(filepath=filepath, storage=FileStore.local,
                    **{"category": FileCategory.image, "privacy": Privacy.public, **kwargs})

    primary = image("b.jpg", primary=True, has_thumbnail=True)
    add_asset("Primary", image("a.jpg", has_thumbnail=True), primary)
    public = image("b.jpg", has_thumbnail=True)
    add_asset("Private primary", image("a.jpg", primary=True, privacy=Privacy.private), public)
    add_asset("Deleted primary", image("a.jpg", primary=True, is_deleted=True))
    no_thumbnail = image("a.JPG")
    add_asset("No thumbnail", no_thumbnail)
    add_asset("Undisplayable", image("a.tiff"))
    add_asset("Not an image", image("a.jpg", category=FileCategory.dump))
    db_session.commit()

    response = anonymous_client.get("/public-search.json")
    assert {asset["name"]: asset["image"] for asset in response.json["assets"]} == {
        "Primary": f"/files/{primary.id}/thumb",
        "Private primary": f"/files/{public.id}/thumb",
        "Deleted primary": None,
        "No thumbnail": f"/files/{no_thumbnail.id}",
        "Undisplayable": None,
        "Not an image": None,
    }


def test_public_magdb_stats(client: FlaskClient, db_session):
    Magazine.get_or_create("Older Magazine")
    magazine, _ = Magazine.get_or_create("Newer Magazine")
    version = MagazineIssueVersion(magazine_issue=MagazineIssue(magazine=magazine))
    logo = File(filepath="newer_logo.svg", storage=FileStore.local, category=FileCategory.logo,
                background_color=BackgroundColor.dark)
    db_session.add(MagazineIssueVersionFiles(
        magazine_issue_version=version, file=logo, file_type=MagDBFileType.logo,
    ))
    db_session.commit()

    response = client.get("/public-magdb/stats.json")
    assert response.status_code == 200
    assert response.json["magazine_count"] == 2
    latest = response.json["latest_magazine"]
    assert latest["title"] == "Newer Magazine"
    assert latest["slug"] == "newer-magazine"
    assert latest["logo"]["url"].endswith("newer_logo.svg")
    assert latest["logo"]["background_color"] == "dark"


@pytest.mark.parametrize("url,expected", [
    ("/asset/12-foo", "/asset/12-foo"),
    ("/asset/?page=2&sort=1", "/asset/?page=2&sort=1"),
    ("http://localhost/event_store/authorize?key=x", "/event_store/authorize?key=x"),
    ("https://localhost/asset/", "/asset/"),
    (None, None),
    ("", None),
    ("asset/", None),
    ("//evil.example/", None),
    ("///evil.example/", "/evil.example/"),
    ("/\\evil.example/", None),
    ("/\t/evil.example/", None),
    ("https://evil.example/", None),
    ("https://localhost@evil.example/", None),
    ("http:/evil.example/", "/evil.example/"),
    ("javascript:alert(1)", None),
])
def test_safe_next_path(url, expected):
    assert safe_next_path(url, "localhost") == expected


def test_login_when_logged_in_goes_to_next(client: FlaskClient):
    response = client.get("/login/github", query_string={"next": "/asset/?page=2&sort=1"})
    assert response.status_code == 302
    assert response.location == "/asset/?page=2&sort=1"


def test_login_when_logged_in_rejects_foreign_next(client: FlaskClient):
    response = client.get("/login/github", query_string={"next": "https://evil.example/"})
    assert response.status_code == 302
    assert response.location == "/"


def test_login_goes_to_next(anonymous_client: FlaskClient, monkeypatch):
    response = anonymous_client.get("/login/github", query_string={"next": "/asset/?page=2&sort=1"})
    assert response.status_code == 302
    assert response.location.startswith("https://github.com/login/oauth/authorize?")
    assert "redirect_uri" not in response.location

    monkeypatch.setattr(github, "_handle_response", lambda: "token")
    monkeypatch.setattr(github, "get", lambda *args, **kwargs: {"id": 1234, "login": "octocat"})
    response = anonymous_client.get("/github-callback", query_string={"code": "code"})
    assert response.status_code == 302
    assert response.location == "/asset/?page=2&sort=1"

    # Used up
    with anonymous_client.session_transaction() as session:
        assert "login_next" not in session


def test_login_without_next_forgets_previous(anonymous_client: FlaskClient, monkeypatch):
    anonymous_client.get("/login/github", query_string={"next": "/asset/"})
    anonymous_client.get("/login/github")

    monkeypatch.setattr(github, "_handle_response", lambda: "token")
    monkeypatch.setattr(github, "get", lambda *args, **kwargs: {"id": 1234, "login": "octocat"})
    response = anonymous_client.get("/github-callback", query_string={"code": "code"})
    assert response.location == "/"


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
