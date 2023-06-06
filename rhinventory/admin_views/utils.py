import typing

from flask import request

from rhinventory.models.asset import Asset
from rhinventory.extensions import db, simple_eval


def get_asset_list_from_request_args() ->  typing.List[Asset]:
    assets: typing.List[Asset] = []
    if "asset_id" in request.values:
        asset_id = simple_eval.eval(request.values["asset_id"])
        if isinstance(asset_id, int) or isinstance(asset_id, str):
            asset_query = db.session.query(Asset).filter(Asset.id == asset_id).one()
            assets = [asset_query]
        else:
            asset_query = db.session.query(Asset).filter(Asset.id.in_(asset_id)).all()
            assets = asset_query
    
    return assets