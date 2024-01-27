import typing

from flask import request
from flask_login import current_user

from rhinventory.models.asset import Asset
from rhinventory.extensions import db, simple_eval
from rhinventory.models.enums import HIDDEN_PRIVACIES
from rhinventory.models.file import File


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

def visible_to_current_user(obj: Asset | File) -> bool:
    if current_user.is_authenticated and current_user.read_access:
        return True
    
    if obj.privacy in HIDDEN_PRIVACIES:
        return False

    return True
