import pytest
from flask.testing import FlaskClient

from rhinventory.db import Asset
from rhinventory.models.asset import AssetCategory

VARIANTS = ["", "ha", "ucm", "small", "small-ha", "small-ucm", "big", "big-ha", "big-ucm"]


@pytest.fixture()
def asset(db_session) -> Asset:
    asset = Asset(id=3175, organization_id=1, category=AssetCategory.game, name="Super Mario Bros. 3")
    db_session.add(asset)
    db_session.commit()
    return asset


def test_labels_page(client: FlaskClient, asset):
    response = client.get("/asset/3175/labels/")

    assert response.status_code == 200
    assert "Super Mario Bros. 3" in response.text
    for variant in VARIANTS:
        url = "/label/asset/3175" + (f"-{variant}" if variant else "")
        code = "3175" + (f"-{variant}" if variant else "")
        assert f'<img src="{url}"' in response.text
        assert f"codes={code}\"" in response.text


def test_labels_page_not_found(client: FlaskClient):
    assert client.get("/asset/3175/labels/").status_code == 404


def test_labels_page_needs_write_access(client: FlaskClient, read_only_user, asset):
    response = client.get("/asset/3175/labels/")

    assert response.status_code == 302


def test_asset_page_links_to_labels_page(client: FlaskClient, asset):
    response = client.get("/asset/3175")

    assert 'href="/asset/3175/labels/"' in response.text
