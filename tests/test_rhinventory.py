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

from rhinventory.models.asset import Asset, AssetCategory
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
    pyzbar,
)
from rhinventory.util import safe_next_path


def test_index(client: FlaskClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "O naší sbírce" in response.data.decode('utf-8')


def test_asset_list(client: FlaskClient):
    response = client.get("/asset/")
    assert response.status_code == 200


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
    # Prepare a dummy file to upload

    data = {
        'category': FileCategory.image.value,
        'privacy': Privacy.private_implicit.value,
        'batch_number': 1,
        'auto_assign': 'y',
        'sort_by_filename': '',
    }

    file_storage = (open('tests/data/test_image.png', 'rb'), 'test_image.png')
    data['files'] = [file_storage]

    response = client.post(
        "/file/upload/",
        data=data,
        content_type='multipart/form-data',
        follow_redirects=True
    )
    # Should redirect to upload result or show result page
    assert response.status_code in (200, 302)


def test_asset_download_files(client: FlaskClient, db_session):
    asset = Asset(organization_id=1, category=AssetCategory.game, name="Zip Test Asset")
    db_session.add(asset)
    db_session.commit()

    files_dir = "files"
    os.makedirs(files_dir, exist_ok=True)
    filepath = "test_download_file.bin"
    contents = b"test zip" * 1000
    with open(os.path.join(files_dir, filepath), 'wb') as f:
        f.write(contents)

    file = File(
        filepath=filepath,
        storage=FileStore.local,
        category=FileCategory.dump,
        asset_id=asset.id,
    )
    db_session.add(file)
    db_session.commit()
    asset_id = asset.id

    response = client.get(f"/asset/download_files/?asset_id=[{asset_id}]")
    assert response.status_code == 200
    assert response.mimetype == "application/zip"

    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        assert zf.namelist() == [f"hh{asset_id}/{filepath}"]
        assert zf.read(f"hh{asset_id}/{filepath}") == contents


def test_file_details_store_not_configured(client: FlaskClient, app, db_session):
    """A file in a store this instance has no location for still has a details page."""
    app.config['FILE_STORE_LOCATIONS'] = {"local": "files", "local_nas": None}

    file = File(
        filepath="uploads/on_the_nas.png",
        storage=FileStore.local_nas,
        category=FileCategory.image,
        has_thumbnail=True,
    )
    db_session.add(file)
    db_session.commit()

    response = client.get(f"/file/details/?id={file.id}")
    assert response.status_code == 200
    assert "which is not configured" in response.data.decode('utf-8')

    with pytest.raises(FileStoreNotConfigured):
        file.full_filepath


TEST_PHOTOS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "test_photos")


@pytest.fixture()
def zbar():
    """Barcode detection silently does nothing without zbar, so fail loudly instead."""
    assert pyzbar is not None, "pyzbar failed to import, is the zbar library installed? (e.g. libzbar0 on Debian/Ubuntu)"


@pytest.mark.parametrize("filename, asset_id", [
    ("hh10461.jpg", 10461),
    ("hh10480.jpg", 10480),
    ("hh10509.jpg", 10509),
])
def test_read_rh_barcode(app, zbar, filename, asset_id):
    app.config['FILE_STORE_LOCATIONS'] = {"local": TEST_PHOTOS_DIR}

    with app.app_context():
        file = File(
            filepath=filename,
            storage=FileStore.local,
            category=FileCategory.image,
        )
        assert file.read_rh_barcode() == asset_id


def test_upload_result_rerun_auto_assign(client: FlaskClient, app, db_session, zbar, tmp_path):
    """Rerunning auto assign from the upload result page assigns images that weren't assigned yet."""
    app.config['FILE_STORE_LOCATIONS'] = {"local": str(tmp_path)}
    os.makedirs(tmp_path / "uploads")
    # Without an hh code in the filename, so the barcode gets read
    shutil.copy(os.path.join(TEST_PHOTOS_DIR, "hh10461.jpg"), tmp_path / "uploads" / "IMG_0001.jpg")

    asset = Asset(id=10461, organization_id=1, category=AssetCategory.game, name="Barcode Test Asset")
    file = File(
        filepath="uploads/IMG_0001.jpg",
        storage=FileStore.local,
        category=FileCategory.image,
        batch_number=42,
    )
    db_session.add_all([asset, file])
    db_session.commit()
    file_id = file.id

    response = client.get("/file/upload/result?batch_number=42")
    assert response.status_code == 200
    assert "Rerun auto assign" in response.data.decode('utf-8')

    response = client.post("/file/upload/result/rerun_auto_assign?batch_number=42", follow_redirects=True)
    assert response.status_code == 200
    assert "1 assigned to assets" in response.data.decode('utf-8')

    file = db_session.get(File, file_id)
    assert file.asset_id == 10461
    assert file.filepath == "assets/10461/IMG_0001.jpg"
    assert (tmp_path / "assets" / "10461" / "IMG_0001.jpg").exists()


def test_file_upload_assigns_by_filename(client: FlaskClient, app, db_session, tmp_path):
    """Uploaded files of any category get assigned by an hh code at the start of their filename,
    and the result page points out missing assets and suggests looser codes."""
    app.config['FILE_STORE_LOCATIONS'] = {"local": str(tmp_path)}
    asset = Asset(id=10461, organization_id=1, category=AssetCategory.game, name="Filename Test Asset")
    db_session.add(asset)
    db_session.commit()

    response = client.post("/file/upload/", data={
        'category': FileCategory.dump.value,
        'privacy': Privacy.private_implicit.value,
        'batch_number': 43,
        'auto_assign': 'y',
        'files': [
            (io.BytesIO(b"assigned"), "hh10461_dump.bin"),
            (io.BytesIO(b"missing asset"), "hh99999.bin"),
            (io.BytesIO(b"suggested"), "IMG_rh10461.bin"),
        ],
    }, content_type='multipart/form-data')
    assert response.status_code == 302

    files = {f.filename: f for f in db_session.query(File).filter(File.batch_number == 43)}
    assert files["hh10461_dump.bin"].asset_id == 10461
    assert files["hh99999.bin"].asset_id is None
    assert files["IMG_rh10461.bin"].asset_id is None

    html = client.get("/file/upload/result?batch_number=43&auto_assign=True").data.decode('utf-8')
    assert "Assigned from filename" in html
    assert "barcode not read" not in html
    assert "Filename says hh99999, but that asset doesn't exist" in html
    assert "Filename suggests" in html
    assert f"/file/assign/?id={files['IMG_rh10461.bin'].id}&amp;asset_id=10461" in html


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
