from flask.testing import FlaskClient

from rhinventory.models.asset import Asset


def test_set_parent_bulk(client: FlaskClient, db_session, make_assets):
    parent, first, second = make_assets(3)

    response = client.post("/asset/set_parent_bulk/", data={
        "asset_id": f"{first},{second}",
        "parent_asset_id": str(parent),
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "Parent for 2 assets set to be" in response.data.decode('utf-8')

    db_session.expire_all()
    assert db_session.get(Asset, first).parent_id == parent
    assert db_session.get(Asset, second).parent_id == parent


def test_set_parent_bulk_rejects_missing_parent(client: FlaskClient, db_session, make_assets):
    (asset_id,) = make_assets(1)

    response = client.post("/asset/set_parent_bulk/", data={
        "asset_id": str(asset_id),
        "parent_asset_id": "999",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "Asset with id 999 not found." in response.data.decode('utf-8')

    db_session.expire_all()
    assert db_session.get(Asset, asset_id).parent_id is None
