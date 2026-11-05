from flask.testing import FlaskClient

from rhinventory.models.asset import Asset, AssetCategory
from rhinventory.models.asset_attributes import AssetTag, Company
from rhinventory.models.enums import Privacy as AssetPrivacy
from rhinventory.models.file import File, FileCategory, FileStore, Privacy


def test_public_search(anonymous_client: FlaskClient, db_session):
    public_tag = AssetTag(name="Public Tag", description="Tag description", is_collection=True)
    hidden_tag = AssetTag(name="Hidden Tag")
    public_asset = Asset(
        organization_id=1, category=AssetCategory.computer, custom_code=12, name="Public Asset",
        description="Some **bold** text", note="A note", product_codes=["ABC-1"], serial="123",
        _privacy=AssetPrivacy.public, tags=[public_tag], companies=[Company(name="Tesla")],
    )
    db_session.add_all([
        public_asset,
        Asset(organization_id=1, category=AssetCategory.game, name="Private Asset",
              _privacy=AssetPrivacy.private, tags=[public_tag, hidden_tag]),
        Asset(organization_id=1, category=AssetCategory.game, name="Implicitly Private Asset",
              tags=[hidden_tag]),
        Asset(organization_id=1, category=AssetCategory.game, name="Unlinked Asset",
              _privacy=AssetPrivacy.unlinked, tags=[hidden_tag]),
    ])
    db_session.commit()

    response = anonymous_client.get("/public-search.json")
    assert response.status_code == 200
    assert [asset["name"] for asset in response.json["assets"]] == ["Public Asset"]
    asset = response.json["assets"][0]
    assert asset["id"] == public_asset.id
    assert asset["slug"] == "public-asset"
    assert asset["code"] == "PC12"
    assert asset["product_codes"] == ["ABC-1"]
    assert asset["description"] == "Some bold text"
    assert asset["note"] == "A note"
    assert asset["tags"] == ["Public Tag"]
    assert asset["companies"] == ["Tesla"]
    assert asset["image"] is None

    assert [tag["name"] for tag in response.json["tags"]] == ["Public Tag"]
    tag = response.json["tags"][0]
    assert tag["description"] == "Tag description"
    assert tag["is_collection"] is True
    assert tag["list_path"] == "/asset/?flt1_45=Public+Tag"


def test_public_search_images(anonymous_client: FlaskClient, db_session):
    def add_asset(name: str, *files: File) -> None:
        db_session.add(Asset(organization_id=1, category=AssetCategory.game, name=name,
                             _privacy=AssetPrivacy.public, files=list(files)))

    def image(filepath: str, **kwargs) -> File:
        return File(filepath=filepath, storage=FileStore.local,
                    **{"category": FileCategory.image, "privacy": Privacy.public, **kwargs})

    primary = image("b.jpg", primary=True, has_thumbnail=True)
    add_asset("Primary", image("a.jpg", has_thumbnail=True), primary)
    public = image("b.jpg", has_thumbnail=True)
    add_asset("Private primary", image("a.jpg", primary=True, privacy=Privacy.private), public)
    add_asset("Deleted primary", image("a.jpg", primary=True, is_deleted=True))
    no_thumbnail = image("a.JPG")
    add_asset("No thumbnail", no_thumbnail)
    add_asset("Undisplayable", image("a.tiff"))
    add_asset("Not an image", image("a.jpg", category=FileCategory.dump))
    db_session.commit()

    response = anonymous_client.get("/public-search.json")
    assert {asset["name"]: asset["image"] for asset in response.json["assets"]} == {
        "Primary": f"/files/{primary.id}/thumb",
        "Private primary": f"/files/{public.id}/thumb",
        "Deleted primary": None,
        "No thumbnail": f"/files/{no_thumbnail.id}",
        "Undisplayable": None,
        "Not an image": None,
    }
