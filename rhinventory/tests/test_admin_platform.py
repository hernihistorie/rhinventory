from urllib.parse import parse_qs, urlparse

from flask.testing import FlaskClient

from rhinventory.models.asset_attributes import Platform


def test_create_platform_from_name_only(client: FlaskClient, db_session):
    # This is what the inline "New" button on the asset form sends
    response = client.post("/platform/new/", data={"name": "Game Boy Color"})
    assert response.status_code == 302

    platform = db_session.query(Platform).one()
    assert platform.name == "Game Boy Color"
    assert platform.slug == "game-boy-color"
    # The inline "New" button reads the new id from the redirect
    assert parse_qs(urlparse(response.location).query)["id"] == [str(platform.id)]


def test_renaming_platform_updates_slug(client: FlaskClient, db_session):
    platform = Platform.from_name("PC")
    db_session.add(platform)
    db_session.commit()

    response = client.post(f"/platform/edit/?id={platform.id}", data={"name": "IBM PC"})
    assert response.status_code == 302

    db_session.expire_all()
    platform = db_session.get(Platform, platform.id)
    assert platform.slug == "ibm-pc"
