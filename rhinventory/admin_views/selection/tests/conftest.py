import pytest

from rhinventory.models.asset import Asset, AssetCategory


@pytest.fixture()
def make_assets(db_session):
    """Create `count` assets, returning their ids."""
    def make(count: int, category: AssetCategory = AssetCategory.game, location_id: int | None = None) -> list[int]:
        assets = [
            Asset(organization_id=1, category=category, name=f"Selection Test {i}", location_id_new=location_id)
            for i in range(count)
        ]
        db_session.add_all(assets)
        db_session.commit()
        return [asset.id for asset in assets]
    return make


@pytest.fixture()
def make_location(db_session):
    """Create a location asset, optionally inside another, returning its id."""
    def make(name: str, inside: int | None = None) -> int:
        location = Asset(organization_id=1, category=AssetCategory.location, name=name, location_id_new=inside)
        db_session.add(location)
        db_session.commit()
        return location.id
    return make
