from datetime import datetime

from flask import Response, flash, redirect, request, url_for
from flask_admin import expose
from flask_login import current_user
from sqlalchemy import func, nulls_last

from rhinventory.admin_views.utils import get_asset_list_from_request_args
from rhinventory.extensions import db
from rhinventory.models.asset import Asset
from rhinventory.models.asset_attributes import AssetTag
from rhinventory.models.log import LogEvent, log
from rhinventory.util import require_write_access


class AddTagMixin:
    def selection_tag_choices(self) -> list[dict[str, int | str]]:
        """Tags offered by the selection panel's tag picker, most recently used first."""
        tags = db.session.query(AssetTag).order_by(nulls_last(AssetTag.last_used.desc())).all()
        return [{'id': tag.id, 'name': tag.name} for tag in tags]

    @expose('/add_tag_bulk/', methods=['POST'])
    @require_write_access
    def add_tag_bulk(self) -> Response:
        """Add one tag to the selected assets.

        The tag is given either as `tag_id`, or as `new_tag_name`, which reuses
        an existing tag of that name (case-insensitive) or creates a new one.
        """
        tag_id = request.form.get('tag_id', '').strip()
        new_tag_name = request.form.get('new_tag_name', '').strip()

        asset_tag: AssetTag | None
        if tag_id:
            asset_tag = db.session.get(AssetTag, int(tag_id)) if tag_id.isdigit() else None
            if not asset_tag:
                flash(f"Tag with id {tag_id} not found.", 'error')
                return redirect(url_for('.index_view'))
        elif new_tag_name:
            asset_tag = db.session.query(AssetTag) \
                .filter(func.lower(AssetTag.name) == new_tag_name.lower()) \
                .order_by(AssetTag.id).first()
            if not asset_tag:
                asset_tag = AssetTag(name=new_tag_name)
                db.session.add(asset_tag)
                db.session.flush()
                flash(f"Created tag {asset_tag}.", 'success')
        else:
            flash("Choose a tag to add.", 'error')
            return redirect(url_for('.index_view'))

        bulk_datetime = datetime.utcnow()
        assets: list[Asset] = get_asset_list_from_request_args()
        assets_to_tag = [asset for asset in assets if asset_tag not in asset.tags]
        for asset in assets_to_tag:
            asset.tags.append(asset_tag)
            db.session.add(asset)
            log(LogEvent.Update, object=asset, user=current_user, is_bulk=True,
                bulk_datetime=bulk_datetime.isoformat(), added_tag_id=asset_tag.id)
        asset_tag.last_used = datetime.now()
        db.session.add(asset_tag)
        db.session.commit()

        message = f"Given {len(assets_to_tag)} assets the tag {asset_tag}."
        already_tagged = len(assets) - len(assets_to_tag)
        if already_tagged:
            message += f" {already_tagged} already had it."
        flash(message, 'success')

        return redirect(url_for('.index_view'))
