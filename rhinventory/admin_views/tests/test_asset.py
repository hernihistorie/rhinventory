import io
import os
import zipfile

from flask.testing import FlaskClient

from rhinventory.models.asset import Asset, AssetCategory
from rhinventory.models.file import File, FileCategory, FileStore


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
