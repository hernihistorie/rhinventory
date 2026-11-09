from flask.testing import FlaskClient

from rhinventory.extensions import github


def test_login_when_logged_in_goes_to_next(client: FlaskClient):
    response = client.get("/login/github", query_string={"next": "/asset/?page=2&sort=1"})
    assert response.status_code == 302
    assert response.location == "/asset/?page=2&sort=1"


def test_login_when_logged_in_rejects_foreign_next(client: FlaskClient):
    response = client.get("/login/github", query_string={"next": "https://evil.example/"})
    assert response.status_code == 302
    assert response.location == "/"


def test_login_goes_to_next(anonymous_client: FlaskClient, monkeypatch):
    response = anonymous_client.get("/login/github", query_string={"next": "/asset/?page=2&sort=1"})
    assert response.status_code == 302
    assert response.location.startswith("https://github.com/login/oauth/authorize?")
    assert "redirect_uri" not in response.location

    monkeypatch.setattr(github, "_handle_response", lambda: "token")
    monkeypatch.setattr(github, "get", lambda *args, **kwargs: {"id": 1234, "login": "octocat"})
    response = anonymous_client.get("/github-callback", query_string={"code": "code"})
    assert response.status_code == 302
    assert response.location == "/asset/?page=2&sort=1"

    # Used up
    with anonymous_client.session_transaction() as session:
        assert "login_next" not in session


def test_login_without_next_forgets_previous(anonymous_client: FlaskClient, monkeypatch):
    anonymous_client.get("/login/github", query_string={"next": "/asset/"})
    anonymous_client.get("/login/github")

    monkeypatch.setattr(github, "_handle_response", lambda: "token")
    monkeypatch.setattr(github, "get", lambda *args, **kwargs: {"id": 1234, "login": "octocat"})
    response = anonymous_client.get("/github-callback", query_string={"code": "code"})
    assert response.location == "/"
