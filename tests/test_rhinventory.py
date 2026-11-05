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


def test_file_upload(client: FlaskClient, test_image):
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

    file_storage = (open(test_image, 'rb'), 'test_image.png')
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


def test_upload_result_rerun_auto_assign(client: FlaskClient, app, db_session, zbar, test_photos_dir, tmp_path):
    """Rerunning auto assign from the upload result page assigns images that weren't assigned yet."""
    app.config['FILE_STORE_LOCATIONS'] = {"local": str(tmp_path)}
    os.makedirs(tmp_path / "uploads")
    # Without an hh code in the filename, so the barcode gets read
    shutil.copy(test_photos_dir / "hh10461.jpg", tmp_path / "uploads" / "IMG_0001.jpg")

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


@pytest.fixture()
def unassigned_file(app, db_session, tmp_path) -> File:
    """A file on disk not assigned to anything, and asset 10461 to assign it to."""
    app.config['FILE_STORE_LOCATIONS'] = {"local": str(tmp_path)}
    os.makedirs(tmp_path / "uploads")
    (tmp_path / "uploads" / "dump.bin").write_bytes(b"data")

    asset = Asset(id=10461, organization_id=1, category=AssetCategory.game, name="Target Asset")
    file = File(filepath="uploads/dump.bin", storage=FileStore.local, category=FileCategory.dump)
    db_session.add_all([asset, file])
    db_session.commit()
    return file


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


LOOKUP_URLS = ["/asset/ajax/lookup/?name=parent&query=Hidden", "/file/ajax/lookup/?name=asset&query=Hidden"]


@pytest.mark.parametrize("url", LOOKUP_URLS)
def test_asset_lookup_hidden_from_anonymous(anonymous_client: FlaskClient, db_session, url):
    db_session.add(Asset(organization_id=1, category=AssetCategory.game, name="Hidden", privacy=AssetPrivacy.private))
    db_session.commit()

    response = anonymous_client.get(url)
    assert response.status_code == 403
    assert b"Hidden" not in response.data


@pytest.mark.parametrize("url", LOOKUP_URLS)
def test_asset_lookup_hidden_from_read_only_users(client: FlaskClient, read_only_user, url):
    assert client.get(url).status_code == 403


@pytest.mark.parametrize("url", LOOKUP_URLS)
def test_asset_lookup_available_with_write_access(client: FlaskClient, db_session, url):
    db_session.add(Asset(organization_id=1, category=AssetCategory.game, name="Hidden", privacy=AssetPrivacy.private))
    db_session.commit()

    response = client.get(url)
    assert response.status_code == 200
    assert len(response.get_json()) == 1


def asset_lookup(client: FlaskClient, query: str, **kwargs) -> list[int]:
    response = client.get("/file/ajax/lookup/", query_string={"name": "asset", "query": query, **kwargs})
    assert response.status_code == 200
    return [asset_id for asset_id, _ in response.get_json()]


def test_asset_lookup_search(client: FlaskClient, db_session):
    db_session.add_all([
        Asset(id=123, organization_id=1, category=AssetCategory.game, name="Alpha"),
        Asset(id=5123, organization_id=1, category=AssetCategory.game, name="Beta"),
        Asset(id=6000, organization_id=1, category=AssetCategory.game, name="Game 123"),
        Asset(id=7000, organization_id=1, category=AssetCategory.game, name="100% Game"),
    ])
    db_session.commit()

    # The exact asset comes first, then name matches from newest; ids only match exactly
    assert asset_lookup(client, "123") == [123, 6000]
    assert asset_lookup(client, "hh123") == [123]
    assert asset_lookup(client, "RH00123") == [123]
    assert asset_lookup(client, "game") == [7000, 6000]
    assert asset_lookup(client, "100%") == [7000]
    assert asset_lookup(client, "%") == [7000]
    assert asset_lookup(client, "_") == []
    assert asset_lookup(client, "game", limit=1, offset=1) == [6000]
    assert asset_lookup(client, "9" * 40) == []


def test_file_details_has_assign_form_without_listing_assets(client: FlaskClient, db_session, unassigned_file):
    html = client.get(f"/file/details/?id={unassigned_file.id}").data.decode('utf-8')

    assert f'action="/file/assign/?id={unassigned_file.id}"' in html
    assert 'data-role="select2-ajax"' in html
    assert 'value="Assign"' in html
    assert "Target Asset" not in html


def test_file_details_preselects_current_asset(client: FlaskClient, db_session, unassigned_file):
    unassigned_file.asset_id = 10461
    db_session.commit()

    html = client.get(f"/file/details/?id={unassigned_file.id}").data.decode('utf-8')
    assert 'value="Re-assign"' in html
    assert 'name="asset_id"' in html and 'value="10461"' in html


@pytest.mark.parametrize("filepath, preselected", [
    ("uploads/hh10461.bin", True),
    ("uploads/IMG_rh10461.bin", True),
    ("uploads/hh99999.bin", False),
])
def test_file_details_preselects_asset_from_filename(client: FlaskClient, db_session, unassigned_file, filepath, preselected):
    unassigned_file.filepath = filepath
    db_session.commit()

    html = client.get(f"/file/details/?id={unassigned_file.id}").data.decode('utf-8')
    assert ('value="10461"' in html) == preselected


def test_file_details_assign_form_hidden_from_anonymous(anonymous_client: FlaskClient, db_session, unassigned_file):
    unassigned_file.privacy = Privacy.public
    db_session.commit()

    response = anonymous_client.get(f"/file/details/?id={unassigned_file.id}")
    assert response.status_code == 200
    assert b"select2-ajax" not in response.data


def test_file_details_assign_form_hidden_when_unusable(client: FlaskClient, app, db_session, unassigned_file):
    url = f"/file/details/?id={unassigned_file.id}"
    assert b"select2-ajax" in client.get(url).data

    unassigned_file.is_deleted = True
    db_session.commit()
    assert b"select2-ajax" not in client.get(url).data

    unassigned_file.is_deleted = False
    db_session.commit()
    app.config['FILE_STORE_LOCATIONS'] = {"local": None}
    assert b"select2-ajax" not in client.get(url).data


def test_file_details_rejects_post(anonymous_client: FlaskClient, db_session, unassigned_file):
    unassigned_file.privacy = Privacy.public
    db_session.commit()

    response = anonymous_client.post(f"/file/details/?id={unassigned_file.id}", data={"asset_id": "10461"})
    assert response.status_code == 405
    db_session.refresh(unassigned_file)
    assert unassigned_file.asset_id is None


def test_file_assign_requires_write_access(client: FlaskClient, read_only_user, db_session, unassigned_file):
    client.post(f"/file/assign/?id={unassigned_file.id}", data={"asset_id": "10461"})
    db_session.refresh(unassigned_file)
    assert unassigned_file.asset_id is None


def test_file_assign_form(client: FlaskClient, db_session, tmp_path, unassigned_file):
    response = client.post(f"/file/assign/?id={unassigned_file.id}", data={"asset_id": "10461"}, follow_redirects=True)
    assert response.status_code == 200
    assert "File assigned to asset #10461" in response.data.decode('utf-8')

    db_session.refresh(unassigned_file)
    assert unassigned_file.asset_id == 10461
    assert unassigned_file.filepath == "assets/10461/dump.bin"
    assert (tmp_path / "assets" / "10461" / "dump.bin").exists()


def test_file_assign_by_query_string(client: FlaskClient, db_session, unassigned_file):
    """The buttons on the upload result page pass asset_id in the URL."""
    response = client.post(f"/file/assign/?id={unassigned_file.id}&asset_id=10461&refresh=True")
    assert response.headers['HX-Refresh'] == 'true'

    db_session.refresh(unassigned_file)
    assert unassigned_file.asset_id == 10461


@pytest.mark.parametrize("asset_id", ["", "abc", "0", "99999", "9" * 40])
def test_file_assign_invalid_asset(client: FlaskClient, db_session, unassigned_file, asset_id):
    response = client.post(f"/file/assign/?id={unassigned_file.id}", data={"asset_id": asset_id}, follow_redirects=True)
    assert response.status_code == 200
    assert "Failed to assign file to asset" in response.data.decode('utf-8')

    db_session.refresh(unassigned_file)
    assert unassigned_file.asset_id is None


def test_file_assign_missing_asset_id(client: FlaskClient, db_session, unassigned_file):
    response = client.post(f"/file/assign/?id={unassigned_file.id}", follow_redirects=True)
    assert "Failed to assign file to asset" in response.data.decode('utf-8')


def test_file_assign_failure_refreshes_htmx_page(client: FlaskClient, db_session, unassigned_file):
    response = client.post(f"/file/assign/?id={unassigned_file.id}&refresh=True", data={"asset_id": "abc"})
    assert response.status_code == 200
    assert response.headers['HX-Refresh'] == 'true'


def test_file_assign_to_same_asset_keeps_filename(client: FlaskClient, db_session, unassigned_file):
    url = f"/file/assign/?id={unassigned_file.id}"
    client.post(url, data={"asset_id": "10461"})
    client.post(url, data={"asset_id": "10461"})

    db_session.refresh(unassigned_file)
    assert unassigned_file.filepath == "assets/10461/dump.bin"


def test_file_reassign_moves_file(client: FlaskClient, db_session, tmp_path, unassigned_file):
    db_session.add(Asset(id=10462, organization_id=1, category=AssetCategory.game, name="Other Asset"))
    db_session.commit()

    url = f"/file/assign/?id={unassigned_file.id}"
    client.post(url, data={"asset_id": "10461"})
    client.post(url, data={"asset_id": "10462"})

    db_session.refresh(unassigned_file)
    assert unassigned_file.asset_id == 10462
    assert unassigned_file.filepath == "assets/10462/dump.bin"
    assert (tmp_path / "assets" / "10462" / "dump.bin").exists()
    assert not (tmp_path / "assets" / "10461" / "dump.bin").exists()


def test_file_assign_refuses_deleted_file(client: FlaskClient, db_session, unassigned_file):
    unassigned_file.is_deleted = True
    db_session.commit()

    response = client.post(f"/file/assign/?id={unassigned_file.id}", data={"asset_id": "10461"}, follow_redirects=True)
    assert "The file has been deleted" in response.data.decode('utf-8')
    db_session.refresh(unassigned_file)
    assert unassigned_file.asset_id is None


def test_file_assign_refuses_unconfigured_store(client: FlaskClient, app, db_session, unassigned_file):
    app.config['FILE_STORE_LOCATIONS'] = {"local": None}

    response = client.post(f"/file/assign/?id={unassigned_file.id}", data={"asset_id": "10461"}, follow_redirects=True)
    assert "which is not configured on this instance" in response.data.decode('utf-8')
    db_session.refresh(unassigned_file)
    assert unassigned_file.asset_id is None


def test_file_edit_form_does_not_list_assets(client: FlaskClient, db_session, unassigned_file):
    response = client.get(f"/file/edit/?id={unassigned_file.id}")
    assert response.status_code == 200
    assert b"select2-ajax" in response.data
    assert b"Target Asset" not in response.data


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
