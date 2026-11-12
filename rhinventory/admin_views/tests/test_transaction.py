from flask.testing import FlaskClient

from rhinventory.models.asset import Asset, AssetCategory
from rhinventory.models.transaction import Transaction


def make_assets(db_session, count: int) -> list[int]:
    assets = [Asset(organization_id=1, category=AssetCategory.game, name=f"Transaction Test {i}") for i in range(count)]
    db_session.add_all(assets)
    db_session.commit()
    return [asset.id for asset in assets]


def test_transaction_list(client: FlaskClient):
    response = client.get("/transaction/")
    assert response.status_code == 200


def test_asset_list_offers_penouze_transaction(client: FlaskClient):
    response = client.get("/asset/")
    assert response.status_code == 200
    assert 'id="selected-create-penouze-transaction-form"' in response.data.decode('utf-8')


def test_create_penouze_transaction(client: FlaskClient, db_session):
    first, second = make_assets(db_session, 2)

    response = client.post("/transaction/create_penouze/", data={
        "asset_id": f"{first},{second}",
        "penouze_id": " 4321 ",
    }, follow_redirects=True)
    assert response.status_code == 200

    transaction = db_session.query(Transaction).filter(Transaction.penouze_id == 4321).one()
    assert transaction.finalized is True
    assert transaction.transaction_type is None
    assert sorted(asset.id for asset in transaction.assets) == [first, second]
    html = response.data.decode('utf-8')
    assert f'Created <a href="/transaction/details/?id={transaction.id}">transaction {transaction.id}</a> ' \
           f'for Peňouze ID 4321 with 2 assets.' in html


def test_create_penouze_transaction_rejects_duplicate(client: FlaskClient, db_session):
    existing = Transaction(penouze_id=55)
    db_session.add(existing)
    db_session.commit()
    (asset_id,) = make_assets(db_session, 1)

    response = client.post("/transaction/create_penouze/", data={
        "asset_id": str(asset_id),
        "penouze_id": "55",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "Peňouze ID 55 already belongs to" in response.data.decode('utf-8')
    assert db_session.query(Transaction).filter(Transaction.penouze_id == 55).count() == 1


def test_create_penouze_transaction_requires_numeric_id(client: FlaskClient, db_session):
    (asset_id,) = make_assets(db_session, 1)

    for penouze_id in ("", "abc"):
        response = client.post("/transaction/create_penouze/", data={
            "asset_id": str(asset_id),
            "penouze_id": penouze_id,
        }, follow_redirects=True)
        assert response.status_code == 200

    assert db_session.query(Transaction).count() == 0
