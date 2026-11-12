import pytest
from flask.testing import FlaskClient

from rhinventory.models.asset import Asset, AssetCategory
from rhinventory.models.file import Privacy


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
