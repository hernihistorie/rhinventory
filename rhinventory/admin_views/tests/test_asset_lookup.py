import pytest
from flask.testing import FlaskClient

from rhinventory.models.asset import Asset, AssetCategory
from rhinventory.models.enums import Privacy as AssetPrivacy


LOOKUP_URLS = ["/asset/ajax/lookup/?name=parent&query=Hidden", "/file/ajax/lookup/?name=asset&query=Hidden"]


@pytest.mark.parametrize("url", LOOKUP_URLS)
def test_asset_lookup_hidden_from_anonymous(anonymous_client: FlaskClient, db_session, url):
    db_session.add(Asset(organization_id=1, category=AssetCategory.game, name="Hidden", privacy=AssetPrivacy.private))
    db_session.commit()

    response = anonymous_client.get(url)
    assert response.status_code == 403
    assert b"Hidden" not in response.data


@pytest.mark.parametrize("url", LOOKUP_URLS)
def test_asset_lookup_hidden_from_read_only_users(client: FlaskClient, read_only_user, url):
    assert client.get(url).status_code == 403


@pytest.mark.parametrize("url", LOOKUP_URLS)
def test_asset_lookup_available_with_write_access(client: FlaskClient, db_session, url):
    db_session.add(Asset(organization_id=1, category=AssetCategory.game, name="Hidden", privacy=AssetPrivacy.private))
    db_session.commit()

    response = client.get(url)
    assert response.status_code == 200
    assert len(response.get_json()) == 1


def asset_lookup(client: FlaskClient, query: str, **kwargs) -> list[int]:
    response = client.get("/file/ajax/lookup/", query_string={"name": "asset", "query": query, **kwargs})
    assert response.status_code == 200
    return [asset_id for asset_id, _ in response.get_json()]


def test_asset_lookup_search(client: FlaskClient, db_session):
    db_session.add_all([
        Asset(id=123, organization_id=1, category=AssetCategory.game, name="Alpha"),
        Asset(id=5123, organization_id=1, category=AssetCategory.game, name="Beta"),
        Asset(id=6000, organization_id=1, category=AssetCategory.game, name="Game 123"),
        Asset(id=7000, organization_id=1, category=AssetCategory.game, name="100% Game"),
    ])
    db_session.commit()

    # The exact asset comes first, then name matches from newest; ids only match exactly
    assert asset_lookup(client, "123") == [123, 6000]
    assert asset_lookup(client, "hh123") == [123]
    assert asset_lookup(client, "RH00123") == [123]
    assert asset_lookup(client, "game") == [7000, 6000]
    assert asset_lookup(client, "100%") == [7000]
    assert asset_lookup(client, "%") == [7000]
    assert asset_lookup(client, "_") == []
    assert asset_lookup(client, "game", limit=1, offset=1) == [6000]
    assert asset_lookup(client, "9" * 40) == []
