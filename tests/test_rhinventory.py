"""
Tests for rhinventory application.

These tests use PostgreSQL running in a podman container.
The conftest.py file manages the container lifecycle and database setup.
"""
import datetime
import io
import os
import re
import shutil
import zipfile

import pytest
from flask.testing import FlaskClient

from rhinventory.extensions import github
from rhinventory.files.hh_code import parse_asset_lookup

from rhinventory.models.asset import Asset, AssetCategory
from rhinventory.models.asset_attributes import AssetTag, Company
from rhinventory.models.enums import Privacy as AssetPrivacy
from rhinventory.models.magdb import Magazine, MagazineIssue, MagazineIssueVersion, \
    MagazineIssueVersionFiles, MagDBFileType
from rhinventory.models.file import (
    BackgroundColor,
    File,
    FileCategory,
    FileStore,
    FileStoreNotConfigured,
    Privacy,
)
from rhinventory.util import safe_next_path


@pytest.mark.parametrize("filename, asset_id", [
    ("hh10461.jpg", 10461),
    ("hh10480.jpg", 10480),
    ("hh10509.jpg", 10509),
])
def test_read_rh_barcode(app, zbar, test_photos_dir, filename, asset_id):
    app.config['FILE_STORE_LOCATIONS'] = {"local": str(test_photos_dir)}

    with app.app_context():
        file = File(
            filepath=filename,
            storage=FileStore.local,
            category=FileCategory.image,
        )
        assert file.read_rh_barcode() == asset_id


@pytest.mark.parametrize("term, asset_id", [
    ("1234", 1234),
    ("01234", 1234),
    (" hh1234 ", 1234),
    ("HH01234", 1234),
    ("rh-1234", 1234),
    ("hh 1234", 1234),
    ("0", None),
    ("hh", None),
    ("", None),
    ("1234a", None),
    ("hh1234 front", None),
    ("rhythm", None),
])
def test_parse_asset_lookup(term, asset_id):
    assert parse_asset_lookup(term) == asset_id


def test_public_magdb_stats(client: FlaskClient, db_session):
    Magazine.get_or_create("Older Magazine")
    magazine, _ = Magazine.get_or_create("Newer Magazine")
    version = MagazineIssueVersion(magazine_issue=MagazineIssue(magazine=magazine))
    logo = File(filepath="newer_logo.svg", storage=FileStore.local, category=FileCategory.logo,
                background_color=BackgroundColor.dark)
    db_session.add(MagazineIssueVersionFiles(
        magazine_issue_version=version, file=logo, file_type=MagDBFileType.logo,
    ))
    db_session.commit()

    response = client.get("/public-magdb/stats.json")
    assert response.status_code == 200
    assert response.json["magazine_count"] == 2
    latest = response.json["latest_magazine"]
    assert latest["title"] == "Newer Magazine"
    assert latest["slug"] == "newer-magazine"
    assert latest["logo"]["url"].endswith("newer_logo.svg")
    assert latest["logo"]["background_color"] == "dark"
