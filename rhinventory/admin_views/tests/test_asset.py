from flask.testing import FlaskClient

from rhinventory.admin_views.asset import AssetView
from rhinventory.models.asset import Asset, AssetCategory
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
