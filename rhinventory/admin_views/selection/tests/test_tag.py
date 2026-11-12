from flask.testing import FlaskClient

from rhinventory.models.asset import Asset
from rhinventory.models.asset_attributes import AssetTag
from rhinventory.models.log import LogItem


def asset_tag_names(db_session, asset_id: int) -> list[str]:
    db_session.expire_all()
    return sorted(tag.name for tag in db_session.get(Asset, asset_id).tags)


def test_asset_list_offers_tags_in_selection_picker(client: FlaskClient, db_session):
    db_session.add(AssetTag(name="Picker <Tag>"))
    db_session.commit()

    response = client.get("/asset/")
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert 'id="selected-tag-choices"' in html
    assert '"name": "Picker \\u003cTag\\u003e"' in html


def test_add_tag_bulk_by_id_skips_already_tagged(client: FlaskClient, db_session, make_assets):
    tag = AssetTag(name="Exhibition")
    db_session.add(tag)
    db_session.commit()
    tag_id = tag.id
    first, second = make_assets(2)
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


def test_add_tag_bulk_creates_new_tag(client: FlaskClient, db_session, make_assets):
    first, second = make_assets(2)

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


def test_add_tag_bulk_new_name_reuses_existing_tag(client: FlaskClient, db_session, make_assets):
    db_session.add(AssetTag(name="Atari"))
    db_session.commit()
    (asset_id,) = make_assets(1)

    response = client.post("/asset/add_tag_bulk/", data={
        "asset_id": str(asset_id),
        "new_tag_name": "atari",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "Created tag" not in response.data.decode('utf-8')

    assert db_session.query(AssetTag).count() == 1
    assert asset_tag_names(db_session, asset_id) == ["Atari"]


def test_add_tag_bulk_rejects_missing_tag(client: FlaskClient, db_session, make_assets):
    (asset_id,) = make_assets(1)

    for data in ({"tag_id": "999"}, {"tag_id": "abc"}, {}):
        response = client.post("/asset/add_tag_bulk/", data={"asset_id": str(asset_id), **data},
                               follow_redirects=True)
        assert response.status_code == 200
        assert asset_tag_names(db_session, asset_id) == []
