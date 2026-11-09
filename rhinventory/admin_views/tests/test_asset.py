import io
import os
import zipfile

from flask.testing import FlaskClient

from rhinventory.models.asset import Asset, AssetCategory
from rhinventory.models.asset_attributes import AssetTag
from rhinventory.models.file import File, FileCategory, FileStore
from rhinventory.models.log import LogItem


def test_asset_list(client: FlaskClient):
    response = client.get("/asset/")
    assert response.status_code == 200


def make_assets(db_session, count: int) -> list[int]:
    assets = [Asset(organization_id=1, category=AssetCategory.game, name=f"Tag Test {i}") for i in range(count)]
    db_session.add_all(assets)
    db_session.commit()
    return [asset.id for asset in assets]


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
