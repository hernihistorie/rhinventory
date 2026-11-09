from flask.testing import FlaskClient


def test_transaction_list(client: FlaskClient):
    response = client.get("/transaction/")
    assert response.status_code == 200
