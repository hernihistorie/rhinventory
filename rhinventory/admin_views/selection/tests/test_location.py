from flask.testing import FlaskClient

from rhinventory.models.asset import Asset, AssetCategory
from rhinventory.models.log import LogItem


def asset_location_id(db_session, asset_id: int) -> int | None:
    db_session.expire_all()
    return db_session.get(Asset, asset_id).location_id_new


def test_asset_list_offers_locations_with_path(client: FlaskClient, db_session, make_location):
    warehouse = make_location("Warehouse")
    shelf = make_location("Shelf <3>", inside=warehouse)

    response = client.get("/asset/")
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert 'id="selected-location-choices"' in html
    assert f'"text": "Warehouse \\u203a Shelf \\u003c3\\u003e (#{shelf})"' in html
    assert f'"text": "Warehouse (#{warehouse})"' in html


def test_location_path_ignores_parent(client: FlaskClient, db_session, make_assets):
    (container,) = make_assets(1)
    box = Asset(organization_id=1, category=AssetCategory.location, name="Box", parent_id=container)
    db_session.add(box)
    db_session.commit()

    html = client.get("/asset/").data.decode('utf-8')
    assert f'"text": "Box (#{box.id})"' in html


def test_set_location_bulk_moves_assets(client: FlaskClient, db_session, make_assets, make_location):
    warehouse = make_location("Warehouse")
    office = make_location("Office")
    (in_office,) = make_assets(1, location_id=office)
    (in_warehouse,) = make_assets(1, location_id=warehouse)
    (nowhere,) = make_assets(1)

    response = client.post("/asset/set_location_bulk/", data={
        "asset_id": f"{in_office},{in_warehouse},{nowhere}",
        "location_id": str(warehouse),
    }, follow_redirects=True)
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert "Moved 2 assets to" in html
    assert "1 of them were in another location. 1 were already there." in html

    for asset_id in (in_office, in_warehouse, nowhere):
        assert asset_location_id(db_session, asset_id) == warehouse
    bulk_logs = db_session.query(LogItem).filter(
        LogItem.table == "Asset", LogItem.extra_json.contains('"assigned_location_asset_id"'),
    ).all()
    assert sorted(log.object_id for log in bulk_logs) == [in_office, nowhere]


def test_set_location_bulk_clear(client: FlaskClient, db_session, make_assets, make_location):
    warehouse = make_location("Warehouse")
    (in_warehouse,) = make_assets(1, location_id=warehouse)
    (nowhere,) = make_assets(1)

    response = client.post("/asset/set_location_bulk/", data={
        "asset_id": f"{in_warehouse},{nowhere}",
        "location_id": str(warehouse),
        "clear": "1",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "Removed 1 assets from their location. 1 had no location." in response.data.decode('utf-8')

    assert asset_location_id(db_session, in_warehouse) is None
    assert asset_location_id(db_session, nowhere) is None


def test_set_location_bulk_rejects_non_location(client: FlaskClient, db_session, make_assets):
    (not_a_location, asset_id) = make_assets(2)

    for location_id in (str(not_a_location), "999", "abc", ""):
        response = client.post("/asset/set_location_bulk/", data={
            "asset_id": str(asset_id),
            "location_id": location_id,
        }, follow_redirects=True)
        assert response.status_code == 200
        assert "not found" in response.data.decode('utf-8')
        assert asset_location_id(db_session, asset_id) is None


def test_set_location_bulk_rejects_loops(client: FlaskClient, db_session, make_location):
    warehouse = make_location("Warehouse")
    shelf = make_location("Shelf", inside=warehouse)

    for location_id in (shelf, warehouse):
        response = client.post("/asset/set_location_bulk/", data={
            "asset_id": str(warehouse),
            "location_id": str(location_id),
        }, follow_redirects=True)
        assert response.status_code == 200
        assert "would end up inside itself" in response.data.decode('utf-8')
        assert asset_location_id(db_session, warehouse) is None
