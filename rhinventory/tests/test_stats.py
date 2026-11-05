import datetime

from flask.testing import FlaskClient

from rhinventory.models.asset import Asset, AssetCategory
from rhinventory.models.enums import Privacy as AssetPrivacy


def test_public_stats(client: FlaskClient, db_session):
    db_session.add_all([
        Asset(organization_id=1, category=AssetCategory.game, name="Private Asset"),
        # Made public before made_public_at existed, must not win over the newer one
        Asset(organization_id=1, category=AssetCategory.game, name="Old Public Asset",
              _privacy=AssetPrivacy.public),
        Asset(organization_id=1, category=AssetCategory.game, name="New Public Asset",
              _privacy=AssetPrivacy.public, made_public_at=datetime.datetime(2026, 1, 1)),
    ])
    db_session.commit()

    response = client.get("/public-stats.json")
    assert response.status_code == 200
    assert response.json["asset_count"] == 3
    latest = response.json["latest_public_asset"]
    assert latest["name"] == "New Public Asset"
    assert latest["slug"] == "new-public-asset"
