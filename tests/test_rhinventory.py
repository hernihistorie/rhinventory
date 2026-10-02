"""
Tests for rhinventory application.

These tests use PostgreSQL running in a podman container.
The conftest.py file manages the container lifecycle and database setup.
"""
import io
import os
import shutil
import zipfile

from flask.testing import FlaskClient

import pytest

from rhinventory.models.asset import Asset, AssetCategory
from rhinventory.models.file import File, FileCategory, FileStore, FileStoreNotConfigured, Privacy


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


@pytest.mark.parametrize("filename, asset_id", [
    ("hh10461.jpg", 10461),
    ("hh10480.jpg", 10480),
    ("hh10509.jpg", 10509),
])
def test_read_rh_barcode(app, filename, asset_id):
    app.config['FILE_STORE_LOCATIONS'] = {"local": TEST_PHOTOS_DIR}

    with app.app_context():
        file = File(
            filepath=filename,
            storage=FileStore.local,
            category=FileCategory.image,
        )
        assert file.read_rh_barcode() == asset_id


def test_upload_result_reprocess_barcodes(client: FlaskClient, app, db_session, tmp_path):
    """Reprocessing barcodes from the upload result page assigns images that weren't assigned yet."""
    app.config['FILE_STORE_LOCATIONS'] = {"local": str(tmp_path)}
    os.makedirs(tmp_path / "uploads")
    shutil.copy(os.path.join(TEST_PHOTOS_DIR, "hh10461.jpg"), tmp_path / "uploads" / "hh10461.jpg")

    asset = Asset(id=10461, organization_id=1, category=AssetCategory.game, name="Barcode Test Asset")
    file = File(
        filepath="uploads/hh10461.jpg",
        storage=FileStore.local,
        category=FileCategory.image,
        batch_number=42,
    )
    db_session.add_all([asset, file])
    db_session.commit()
    file_id = file.id

    response = client.get("/file/upload/result?batch_number=42")
    assert response.status_code == 200
    assert "Reprocess barcodes" in response.data.decode('utf-8')

    response = client.post("/file/upload/result/reprocess_barcodes?batch_number=42", follow_redirects=True)
    assert response.status_code == 200
    assert "1 assigned to assets" in response.data.decode('utf-8')

    file = db_session.get(File, file_id)
    assert file.asset_id == 10461
    assert file.filepath == "assets/10461/hh10461.jpg"
    assert (tmp_path / "assets" / "10461" / "hh10461.jpg").exists()
