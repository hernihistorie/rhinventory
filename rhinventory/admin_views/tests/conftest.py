import os

import pytest

from rhinventory.models.asset import Asset, AssetCategory
from rhinventory.models.file import File, FileCategory, FileStore


@pytest.fixture()
def unassigned_file(app, db_session, tmp_path) -> File:
    """A file on disk not assigned to anything, and asset 10461 to assign it to."""
    app.config['FILE_STORE_LOCATIONS'] = {"local": str(tmp_path)}
    os.makedirs(tmp_path / "uploads")
    (tmp_path / "uploads" / "dump.bin").write_bytes(b"data")

    asset = Asset(id=10461, organization_id=1, category=AssetCategory.game, name="Target Asset")
    file = File(filepath="uploads/dump.bin", storage=FileStore.local, category=FileCategory.dump)
    db_session.add_all([asset, file])
    db_session.commit()
    return file
