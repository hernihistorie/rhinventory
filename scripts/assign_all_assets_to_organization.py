import tqdm

from rhinventory.app import create_app
from rhinventory.extensions import db
from rhinventory.db import Asset

ORGANIZATION_ID = 1

app = create_app()

with app.app_context():
    assets = db.session.query(Asset).filter(Asset.organization_id == None).all()
    for asset in tqdm.tqdm(assets):
        asset.organization_id = ORGANIZATION_ID

    db.session.commit()