"""Bulk actions from the asset list's selection panel."""
from flask.testing import FlaskClient

from rhinventory.models.asset import Asset, AssetCategory
from rhinventory.models.asset_attributes import AssetTag
from rhinventory.models.log import LogItem


def make_assets(db_session, count: int, category: AssetCategory = AssetCategory.game,
                location_id: int | None = None) -> list[int]:
    assets = [
        Asset(organization_id=1, category=category, name=f"Selection Test {i}", location_id_new=location_id)
        for i in range(count)
    ]
    db_session.add_all(assets)
    db_session.commit()
    return [asset.id for asset in assets]


def make_location(db_session, name: str, inside: int | None = None) -> int:
    location = Asset(organization_id=1, category=AssetCategory.location, name=name, location_id_new=inside)
    db_session.add(location)
    db_session.commit()
    return location.id


def asset_tag_names(db_session, asset_id: int) -> list[str]:
    db_session.expire_all()
    return sorted(tag.name for tag in db_session.get(Asset, asset_id).tags)


def asset_location_id(db_session, asset_id: int) -> int | None:
    db_session.expire_all()
    return db_session.get(Asset, asset_id).location_id_new


# Tag

def test_asset_list_offers_tags_in_selection_picker(client: FlaskClient, db_session):
    db_session.add(AssetTag(name="Picker <Tag>"))
    db_session.commit()

    response = client.get("/asset/")
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert 'id="selected-tag-choices"' in html
    assert '"name": "Picker \\u003cTag\\u003e"' in html


def test_add_tag_bulk_by_id_skips_already_tagged(client: FlaskClient, db_session):
    tag = AssetTag(name="Exhibition")
    db_session.add(tag)
    db_session.commit()
    tag_id = tag.id
    first, second = make_assets(db_session, 2)
    first_asset = db_session.get(Asset, first)
    first_asset.tags.append(tag)
    db_session.commit()

    response = client.post("/asset/add_tag_bulk/", data={
        "asset_id": f"{first},{second}",
        "tag_id": str(tag_id),
    }, follow_redirects=True)
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert "Given 1 assets the tag Exhibition. 1 already had it." in html

    assert asset_tag_names(db_session, first) == ["Exhibition"]
    assert asset_tag_names(db_session, second) == ["Exhibition"]
    assert db_session.get(AssetTag, tag_id).last_used is not None
    bulk_logs = db_session.query(LogItem).filter(
        LogItem.table == "Asset", LogItem.extra_json.contains('"added_tag_id"'),
    ).all()
    assert [log.object_id for log in bulk_logs] == [second]


def test_add_tag_bulk_creates_new_tag(client: FlaskClient, db_session):
    first, second = make_assets(db_session, 2)

    response = client.post("/asset/add_tag_bulk/", data={
        "asset_id": f"{first},{second}",
        "new_tag_name": "  Brand new  ",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "Created tag Brand new." in response.data.decode('utf-8')

    tags = db_session.query(AssetTag).filter(AssetTag.name == "Brand new").all()
    assert len(tags) == 1
    assert asset_tag_names(db_session, first) == ["Brand new"]
    assert asset_tag_names(db_session, second) == ["Brand new"]


def test_add_tag_bulk_new_name_reuses_existing_tag(client: FlaskClient, db_session):
    db_session.add(AssetTag(name="Atari"))
    db_session.commit()
    (asset_id,) = make_assets(db_session, 1)

    response = client.post("/asset/add_tag_bulk/", data={
        "asset_id": str(asset_id),
        "new_tag_name": "atari",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "Created tag" not in response.data.decode('utf-8')

    assert db_session.query(AssetTag).count() == 1
    assert asset_tag_names(db_session, asset_id) == ["Atari"]


def test_add_tag_bulk_rejects_missing_tag(client: FlaskClient, db_session):
    (asset_id,) = make_assets(db_session, 1)

    for data in ({"tag_id": "999"}, {"tag_id": "abc"}, {}):
        response = client.post("/asset/add_tag_bulk/", data={"asset_id": str(asset_id), **data},
                               follow_redirects=True)
        assert response.status_code == 200
        assert asset_tag_names(db_session, asset_id) == []


# Location

def test_asset_list_offers_locations_with_path(client: FlaskClient, db_session):
    warehouse = make_location(db_session, "Warehouse")
    shelf = make_location(db_session, "Shelf <3>", inside=warehouse)

    response = client.get("/asset/")
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert 'id="selected-location-choices"' in html
    assert f'"text": "Warehouse \\u203a Shelf \\u003c3\\u003e (#{shelf})"' in html
    assert f'"text": "Warehouse (#{warehouse})"' in html


def test_location_path_ignores_parent(client: FlaskClient, db_session):
    (container,) = make_assets(db_session, 1)
    box = Asset(organization_id=1, category=AssetCategory.location, name="Box", parent_id=container)
    db_session.add(box)
    db_session.commit()

    html = client.get("/asset/").data.decode('utf-8')
    assert f'"text": "Box (#{box.id})"' in html


def test_set_location_bulk_moves_assets(client: FlaskClient, db_session):
    warehouse = make_location(db_session, "Warehouse")
    office = make_location(db_session, "Office")
    (in_office,) = make_assets(db_session, 1, location_id=office)
    (in_warehouse,) = make_assets(db_session, 1, location_id=warehouse)
    (nowhere,) = make_assets(db_session, 1)

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


def test_set_location_bulk_clear(client: FlaskClient, db_session):
    warehouse = make_location(db_session, "Warehouse")
    (in_warehouse,) = make_assets(db_session, 1, location_id=warehouse)
    (nowhere,) = make_assets(db_session, 1)

    response = client.post("/asset/set_location_bulk/", data={
        "asset_id": f"{in_warehouse},{nowhere}",
        "location_id": str(warehouse),
        "clear": "1",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "Removed 1 assets from their location. 1 had no location." in response.data.decode('utf-8')

    assert asset_location_id(db_session, in_warehouse) is None
    assert asset_location_id(db_session, nowhere) is None


def test_set_location_bulk_rejects_non_location(client: FlaskClient, db_session):
    (not_a_location, asset_id) = make_assets(db_session, 2)

    for location_id in (str(not_a_location), "999", "abc", ""):
        response = client.post("/asset/set_location_bulk/", data={
            "asset_id": str(asset_id),
            "location_id": location_id,
        }, follow_redirects=True)
        assert response.status_code == 200
        assert "not found" in response.data.decode('utf-8')
        assert asset_location_id(db_session, asset_id) is None


def test_set_location_bulk_rejects_loops(client: FlaskClient, db_session):
    warehouse = make_location(db_session, "Warehouse")
    shelf = make_location(db_session, "Shelf", inside=warehouse)

    for location_id in (shelf, warehouse):
        response = client.post("/asset/set_location_bulk/", data={
            "asset_id": str(warehouse),
            "location_id": str(location_id),
        }, follow_redirects=True)
        assert response.status_code == 200
        assert "would end up inside itself" in response.data.decode('utf-8')
        assert asset_location_id(db_session, warehouse) is None
