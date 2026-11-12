import pytest
from flask.testing import FlaskClient

from rhinventory.models.file import File, FileCategory, FileStore, FileStoreNotConfigured, Privacy


def test_file_list(client: FlaskClient):
    response = client.get("/file/")
    assert response.status_code == 200


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


def test_file_details_rejects_post(anonymous_client: FlaskClient, db_session, unassigned_file):
    unassigned_file.privacy = Privacy.public
    db_session.commit()

    response = anonymous_client.post(f"/file/details/?id={unassigned_file.id}", data={"asset_id": "10461"})
    assert response.status_code == 405
    db_session.refresh(unassigned_file)
    assert unassigned_file.asset_id is None


def test_file_edit_form_does_not_list_assets(client: FlaskClient, db_session, unassigned_file):
    response = client.get(f"/file/edit/?id={unassigned_file.id}")
    assert response.status_code == 200
    assert b"select2-ajax" in response.data
    assert b"Target Asset" not in response.data
