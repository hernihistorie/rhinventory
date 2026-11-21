import pytest
from flask import Flask
from flask.testing import FlaskClient

from rhinventory.models.file import File, FileCategory, FileStore, Privacy


@pytest.fixture()
def x_accel_redirect(app: Flask):
    app.config["X_ACCEL_REDIRECT_LOCATIONS"] = {"local": "/_files/local/"}


@pytest.fixture()
def files_dir(app: Flask, tmp_path, monkeypatch):
    monkeypatch.setitem(app.config["FILE_STORE_LOCATIONS"], "local", str(tmp_path))
    return tmp_path


def add_file(db_session, filepath: str, **kwargs) -> File:
    file = File(filepath=filepath, storage=FileStore.local, category=FileCategory.dump,
                privacy=Privacy.public, **kwargs)
    db_session.add(file)
    db_session.commit()
    db_session.refresh(file)
    return file


def test_file_sent_by_flask_without_x_accel_redirect(client: FlaskClient, db_session, files_dir):
    (files_dir / "dump.zip").write_bytes(b"dump")
    file = add_file(db_session, "dump.zip")

    response = client.get(f"/files/{file.id}/dump.zip")

    assert response.status_code == 200
    assert response.data == b"dump"
    assert "X-Accel-Redirect" not in response.headers


def test_file_sent_by_nginx(client: FlaskClient, db_session, x_accel_redirect):
    file = add_file(db_session, "2026/HH09587 raw?.zip")

    response = client.get(f"/files/{file.id}")

    assert response.status_code == 200
    assert response.data == b""
    assert response.headers["X-Accel-Redirect"] == "/_files/local/2026/HH09587%20raw%3F.zip"
    assert response.headers["Content-Type"] == "application/zip"
    assert response.headers["Cache-Control"] == "no-cache"


def test_compressed_file_sent_by_nginx_with_encoding(client: FlaskClient, db_session, x_accel_redirect):
    file = add_file(db_session, "dump.tar.gz")

    response = client.get(f"/files/{file.id}/dump.tar.gz")

    assert response.headers["Content-Type"] == "application/x-tar"
    assert response.headers["Content-Encoding"] == "gzip"


def test_unknown_file_type_sent_by_nginx_as_octet_stream(client: FlaskClient, db_session, x_accel_redirect):
    file = add_file(db_session, "dump.hhfloppy")

    response = client.get(f"/files/{file.id}/dump.hhfloppy")

    assert response.headers["Content-Type"] == "application/octet-stream"


def test_thumbnail_sent_by_nginx(client: FlaskClient, db_session, x_accel_redirect):
    file = add_file(db_session, "photo.jpg", has_thumbnail=True)

    response = client.get(f"/files/{file.id}/thumb")

    assert response.headers["X-Accel-Redirect"] == "/_files/local/photo_thumb.jpg"
    assert response.headers["Content-Type"] == "image/jpeg"


def test_file_in_store_nginx_doesnt_serve_sent_by_flask(client: FlaskClient, db_session, app: Flask, files_dir):
    app.config["X_ACCEL_REDIRECT_LOCATIONS"] = {"local_nas": "/_files/local_nas/"}
    (files_dir / "dump.zip").write_bytes(b"dump")
    file = add_file(db_session, "dump.zip")

    response = client.get(f"/files/{file.id}/dump.zip")

    assert response.data == b"dump"
    assert "X-Accel-Redirect" not in response.headers


def test_private_file_not_sent_by_nginx_to_anonymous(anonymous_client: FlaskClient, db_session, x_accel_redirect):
    file = add_file(db_session, "dump.zip")
    file.privacy = Privacy.private
    db_session.commit()

    response = anonymous_client.get(f"/files/{file.id}/dump.zip")

    assert response.status_code == 403
    assert "X-Accel-Redirect" not in response.headers
