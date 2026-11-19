from flask.testing import FlaskClient

from rhinventory.admin_views.asset import AssetView
from rhinventory.models.asset import Asset, AssetCategory
from rhinventory.models.asset_attributes import AssetTag, Platform
from rhinventory.models.enums import Privacy


def test_asset_list(client: FlaskClient):
    response = client.get("/asset/")
    assert response.status_code == 200


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


def test_asset_edit_sets_platforms(client: FlaskClient, db_session):
    platform = Platform.from_name("NES")
    asset = Asset(organization_id=1, category=AssetCategory.game, name="Platform Game")
    db_session.add_all([platform, asset])
    db_session.commit()

    response = client.post(f"/asset/edit/?id={asset.id}", data={
        "organization": "1",
        "category": AssetCategory.game.name,
        "name": "Platform Game",
        "platforms": [str(platform.id)],
    })
    assert response.status_code == 302

    db_session.expire_all()
    assert [p.name for p in db_session.get(Asset, asset.id).platforms] == ["NES"]
    assert db_session.get(Platform, platform.id).last_used is not None

    response = client.get(f"/asset/details/?id={asset.id}")
    html = response.data.decode('utf-8')
    assert "<strong>Platforms</strong>" in html
    assert "NES" in html


def test_asset_list_filters(client: FlaskClient, db_session, app):
    nes, snes = Platform.from_name("NES"), Platform.from_name("SNES")
    tag = AssetTag(name="Boxed")
    on_nes = Asset(organization_id=1, category=AssetCategory.game, name="Plays on NES", platforms=[nes])
    on_snes = Asset(organization_id=1, category=AssetCategory.game, name="Plays on SNES", platforms=[snes], tags=[tag])
    db_session.add_all([on_nes, on_snes])
    db_session.commit()

    asset_view = next(view for view in app.extensions['admin'][0]._views if isinstance(view, AssetView))
    platform_filter_index = next(
        index for index, flt in enumerate(asset_view._filters)
        if flt.column.table.name == 'platforms' and flt.operation() == 'equals'
    )
    html = client.get(f"/asset/?flt1_{platform_filter_index}=NES").data.decode('utf-8')
    assert "Plays on NES" in html
    assert "Plays on SNES" not in html

    # Filters are addressed by index, and the tag filter's is hardcoded in links
    html = client.get("/asset/?flt1_45=Boxed").data.decode('utf-8')
    assert "Plays on SNES" in html
    assert "Plays on NES" not in html


def add_assets(db_session, privacies) -> list[Asset]:
    assets = [
        Asset(organization_id=1, category=AssetCategory.game, name=f"Asset {i}", privacy=privacy)
        for i, privacy in enumerate(privacies)
    ]
    db_session.add_all(assets)
    db_session.commit()
    return assets


def test_asset_details_links_to_list_page(client: FlaskClient, db_session, monkeypatch):
    monkeypatch.setattr(AssetView, "page_size", 2)
    # The list is sorted newest first: pages are [4, 3], [2, 1], [0]
    assets = add_assets(db_session, [Privacy.public] * 5)

    expected_pages = {0: "page=2&amp;", 1: "page=1&amp;", 2: "page=1&amp;", 3: "", 4: ""}
    for index, page in expected_pages.items():
        asset_id = assets[index].id
        response = client.get(f"/asset/{asset_id}")
        html = response.data.decode('utf-8')
        assert "Sbírka předmětů spolku Herní historie" in html
        assert f'href="/asset/?{page}highlight={asset_id}"' in html


def test_asset_details_list_page_skips_private_assets_for_anonymous(anonymous_client: FlaskClient, db_session, monkeypatch):
    monkeypatch.setattr(AssetView, "page_size", 2)
    # Anonymous users only see [2, 0] on the first page
    assets = add_assets(db_session, [Privacy.public, Privacy.private, Privacy.public, Privacy.private])

    asset_id = assets[0].id
    response = anonymous_client.get(f"/asset/{asset_id}")
    assert f'href="/asset/?highlight={asset_id}"' in response.data.decode('utf-8')

    # The highlight script finds the row by its checkbox
    response = anonymous_client.get(f"/asset/?highlight={asset_id}")
    assert f'class="action-checkbox" value="{asset_id}"' in response.data.decode('utf-8')
