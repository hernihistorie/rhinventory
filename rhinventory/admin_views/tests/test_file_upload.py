import io
import os
import shutil

from flask.testing import FlaskClient

from rhinventory.models.asset import Asset, AssetCategory
from rhinventory.models.file import File, FileCategory, FileStore, Privacy


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
