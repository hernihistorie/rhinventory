from flask.testing import FlaskClient

from rhinventory.models.asset import Asset, AssetCategory


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

    for parent_asset_id in ("999", "abc", ""):
        response = client.post("/asset/set_parent_bulk/", data={
            "asset_id": str(asset_id),
            "parent_asset_id": parent_asset_id,
        }, follow_redirects=True)
        assert response.status_code == 200
        assert f"Asset with id {parent_asset_id} not found." in response.data.decode('utf-8')

        db_session.expire_all()
        assert db_session.get(Asset, asset_id).parent_id is None


def test_asset_list_offers_parent_search(client: FlaskClient):
    html = client.get("/asset/").data.decode('utf-8')
    assert 'id="selected-parent-picker" data-url="/asset/ajax/lookup/?name=selection_parent"' in html


def test_parent_search_finds_assets_by_name_and_id(client: FlaskClient, db_session):
    db_session.add_all([
        Asset(id=123, organization_id=1, category=AssetCategory.game, name="Big Box"),
        Asset(id=5000, organization_id=1, category=AssetCategory.game, name="Box 123"),
        Asset(id=6000, organization_id=1, category=AssetCategory.game, name="Cartridge"),
    ])
    db_session.commit()

    def search(query: str) -> list[int]:
        response = client.get("/asset/ajax/lookup/", query_string={"name": "selection_parent", "query": query})
        assert response.status_code == 200
        return [asset_id for asset_id, _ in response.get_json()]

    assert search("box") == [5000, 123]
    assert search("hh123") == [123]
    assert search("123") == [123, 5000]
