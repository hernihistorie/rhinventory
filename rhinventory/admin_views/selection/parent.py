from datetime import datetime

from flask import Response, flash, redirect, request, url_for
from flask_admin import expose
from flask_login import current_user

from rhinventory.admin_views.utils import get_asset_list_from_request_args
from rhinventory.extensions import db
from rhinventory.models.asset import Asset
from rhinventory.models.log import LogEvent, log
from rhinventory.util import require_write_access


class SetParentMixin:
    @expose('/set_parent_bulk/', methods=['POST'])
    @require_write_access
    def set_parent_bulk(self) -> Response:
        parent_asset_id = int(request.form['parent_asset_id'])
        parent_asset: Asset | None = db.session.query(Asset).get(parent_asset_id)
        if not parent_asset:
            flash(f"Asset with id {parent_asset_id} not found.", 'error')
            return redirect(url_for('.index_view'))

        assert isinstance(parent_asset, Asset)

        bulk_datetime = datetime.utcnow()
        assets: list[Asset] = get_asset_list_from_request_args()
        for asset in assets:
            asset.parent_id = parent_asset.id
            db.session.add(asset)
            log(LogEvent.Update, object=asset, user=current_user, is_bulk=True, bulk_datetime=bulk_datetime.isoformat())
        db.session.commit()

        message = f"Parent for {len(assets)} assets set to be {parent_asset}."

        flash(message, "success")

        return redirect(url_for('.index_view'))
