import pytest

from rhinventory.app import create_app

@pytest.fixture()
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
    })

    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


def test_request(client):
    response = client.get("/admin/")
    assert "Vítejte" in response.data.decode('utf-8')