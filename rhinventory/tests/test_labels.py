import io

import pytest
from flask.testing import FlaskClient
from PIL import Image

from rhinventory.db import Asset, Location
from rhinventory.models.asset import AssetCategory
from rhinventory.models.file import pyzbar


@pytest.fixture()
def asset(db_session) -> Asset:
    asset = Asset(id=3175, organization_id=1, category=AssetCategory.game, name="Super Mario Bros. 3")
    db_session.add(asset)
    db_session.commit()
    return asset


# Every label hhprint asks for, see hhprint_url()
@pytest.mark.parametrize("variant, expected_size", [
    ("", (696, 314)),
    ("-small", (696, 112)),
    ("-ha", (696, 314)),
    ("-small-ha", (696, 112)),
    ("-ucm", (696, 314)),
    ("-small-ucm", (696, 112)),
    ("-big", (970, 2147)),
    ("-big-ha", (970, 2147)),
])
def test_asset_label(client: FlaskClient, label_renderer, zbar, asset, variant, expected_size):
    response = client.get(f"/label/asset/3175{variant}")

    assert response.status_code == 200
    assert response.mimetype == "image/png"
    image = Image.open(io.BytesIO(response.data))
    assert image.size == expected_size
    assert [code.data for code in pyzbar.decode(image)] == [b"HH03175"]


def test_asset_label_html(client: FlaskClient, asset):
    response = client.get("/label/asset/3175-small-ha?format=html")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "Super Mario Bros. 3" in response.text
    assert "HH03175" in response.text


@pytest.mark.parametrize("url", [
    "/label/asset/3175-tiny",
    "/label/asset/3175-ha-small",
    "/label/asset/3175-small-",
    "/label/asset/9999",
    "/label/asset/9999-small",
])
def test_asset_label_not_found(client: FlaskClient, asset, url):
    assert client.get(url).status_code == 404


def test_asset_label_without_login(anonymous_client: FlaskClient, label_renderer, asset):
    # @login_required is applied after @app.route, so it doesn't apply, and hhprint may rely on that
    response = anonymous_client.get("/label/asset/3175")

    assert response.status_code == 200
    assert response.mimetype == "image/png"


def test_location_label(client: FlaskClient, label_renderer, zbar, db_session):
    db_session.add(Location(id=12, name="Regál A3"))
    db_session.commit()

    response = client.get("/label/location/12")

    assert response.status_code == 200
    image = Image.open(io.BytesIO(response.data))
    assert image.size == (696, 314)
    assert [code.data for code in pyzbar.decode(image)] == [b"RHL0012"]


def test_location_label_not_found(client: FlaskClient):
    assert client.get("/label/location/12").status_code == 404
