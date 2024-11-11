from rhinventory.extensions import db
from rhinventory.models.asset import Asset


class AssetService:
    @classmethod
    def get_assets(cls, public=True):
        query = db.session.query(Asset).filter_by(public=public)

        result = db.execute(query)

        return result.fetchall()
