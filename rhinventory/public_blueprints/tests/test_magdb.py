from flask.testing import FlaskClient

from rhinventory.models.file import BackgroundColor, File, FileCategory, FileStore
from rhinventory.models.magdb import Magazine, MagazineIssue, MagazineIssueVersion, \
    MagazineIssueVersionFiles, MagDBFileType


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
