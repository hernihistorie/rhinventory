from datetime import datetime

from flask import Response, flash, redirect, request, url_for
from flask_admin import expose
from flask_login import current_user

from rhinventory.admin_views.utils import get_asset_list_from_request_args
from rhinventory.extensions import db
from rhinventory.models.asset import Asset, AssetCategory
from rhinventory.models.log import LogEvent, log
from rhinventory.util import require_write_access


def _containers(asset: Asset) -> list[Asset]:
    """The locations the asset sits in, innermost first."""
    containers: list[Asset] = []
    container = asset.location
    while container and container is not asset and container not in containers:
        containers.append(container)
        container = container.location
    return containers


class SetLocationMixin:
    def selection_location_choices(self) -> list[dict[str, int | str]]:
        """Locations offered by the selection panel's location picker, labelled with their full path."""
        locations = db.session.query(Asset).filter(Asset.category == AssetCategory.location).all()
        choices: list[dict[str, int | str]] = []
        for location in locations:
            path = [location, *_containers(location)]
            label = " › ".join(asset.name for asset in reversed(path))
            choices.append({'id': location.id, 'text': f"{label} (#{location.id})"})
        return sorted(choices, key=lambda choice: str(choice['text']).lower())

    @expose('/set_location_bulk/', methods=['POST'])
    @require_write_access
    def set_location_bulk(self) -> Response:
        """Move the selected assets into a location, or out of theirs with `clear`."""
        assets: list[Asset] = get_asset_list_from_request_args()
        bulk_datetime = datetime.utcnow()

        location: Asset | None = None
        if not request.form.get('clear'):
            location_id = request.form.get('location_id', '').strip()
            location = db.session.get(Asset, int(location_id)) if location_id.isdigit() else None
            if not location or location.category != AssetCategory.location:
                flash(f"Location with id {location_id} not found.", 'error')
                return redirect(url_for('.index_view'))
            looped = [asset for asset in assets if asset is location or asset in _containers(location)]
            if looped:
                flash(f"Can't put {', '.join(str(asset) for asset in looped)} inside {location}, "
                      "as it would end up inside itself.", 'error')
                return redirect(url_for('.index_view'))

        new_location_id = location.id if location else None
        assets_to_move = [asset for asset in assets if asset.location_id_new != new_location_id]
        moved_from_elsewhere = sum(1 for asset in assets_to_move if asset.location_id_new is not None)
        for asset in assets_to_move:
            asset.location = location
            db.session.add(asset)
            log(LogEvent.Update, object=asset, user=current_user, is_bulk=True,
                bulk_datetime=bulk_datetime.isoformat(), assigned_location_asset_id=new_location_id)
        db.session.commit()

        unchanged = len(assets) - len(assets_to_move)
        if location:
            message = f"Moved {len(assets_to_move)} assets to {location}."
            if moved_from_elsewhere:
                message += f" {moved_from_elsewhere} of them were in another location."
            if unchanged:
                message += f" {unchanged} were already there."
        else:
            message = f"Removed {len(assets_to_move)} assets from their location."
            if unchanged:
                message += f" {unchanged} had no location."
        flash(message, 'success')

        return redirect(url_for('.index_view'))
