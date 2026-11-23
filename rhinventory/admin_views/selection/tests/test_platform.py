from flask.testing import FlaskClient

from rhinventory.models.asset import Asset
from rhinventory.models.asset_attributes import Platform


def asset_platform_names(db_session, asset_id: int) -> list[str]:
    db_session.expire_all()
    return sorted(platform.name for platform in db_session.get(Asset, asset_id).platforms)


def test_asset_list_offers_platforms_in_selection_picker(client: FlaskClient, db_session):
    db_session.add(Platform.from_name("ZX Spectrum"))
    db_session.commit()

    response = client.get("/asset/")
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert 'id="selected-platform-choices"' in html
    assert '"name": "ZX Spectrum"' in html


def test_add_platform_bulk_by_id(client: FlaskClient, db_session, make_assets):
    platform = Platform.from_name("Commodore 64")
    db_session.add(platform)
    db_session.commit()
    platform_id = platform.id
    first, second = make_assets(2)

    response = client.post("/asset/add_platform_bulk/", data={
        "asset_id": f"{first},{second}",
        "platform_id": str(platform_id),
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "Given 2 assets the platform Commodore 64." in response.data.decode('utf-8')

    assert asset_platform_names(db_session, first) == ["Commodore 64"]
    assert asset_platform_names(db_session, second) == ["Commodore 64"]
    assert db_session.get(Platform, platform_id).last_used is not None


def test_add_platform_bulk_creates_new_platform_with_slug(client: FlaskClient, db_session, make_assets):
    (asset_id,) = make_assets(1)

    response = client.post("/asset/add_platform_bulk/", data={
        "asset_id": str(asset_id),
        "new_platform_name": "Atari ST",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "Created platform Atari ST." in response.data.decode('utf-8')

    platform = db_session.query(Platform).one()
    assert platform.slug == "atari-st"
    assert asset_platform_names(db_session, asset_id) == ["Atari ST"]
