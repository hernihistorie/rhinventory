"""Shared logic for selection actions which add a named attribute (a tag, a
platform...) to the selected assets, picking an existing one or creating it."""
from datetime import datetime
from typing import Any, Callable

from flask import Response, flash, request
from flask_login import current_user
from sqlalchemy import func, nulls_last

from rhinventory.admin_views.utils import get_asset_list_from_request_args, redirect_back_to_list
from rhinventory.extensions import db
from rhinventory.models.asset import Asset
from rhinventory.models.log import LogEvent, log


def attribute_choices(attribute_class: Any) -> list[dict[str, int | str]]:
    """Attributes offered by a selection panel picker, most recently used first."""
    attributes = db.session.query(attribute_class) \
        .order_by(nulls_last(attribute_class.last_used.desc())).all()
    return [{'id': attribute.id, 'name': attribute.name} for attribute in attributes]


def add_attribute_bulk(
        attribute_class: Any,
        relationship: str,
        noun: str,
        create: Callable[[str], Any] | None = None) -> Response:
    """Add one attribute to the selected assets' `relationship` list.

    The attribute is given either as `<noun>_id`, or as `new_<noun>_name`, which
    reuses an existing attribute of that name (case-insensitive) or creates a new
    one with `create(name)`, by default `attribute_class(name=name)`.
    """
    attribute_id = request.form.get(f'{noun}_id', '').strip()
    new_name = request.form.get(f'new_{noun}_name', '').strip()

    attribute: Any
    if attribute_id:
        attribute = db.session.get(attribute_class, int(attribute_id)) if attribute_id.isdigit() else None
        if not attribute:
            flash(f"{noun.capitalize()} with id {attribute_id} not found.", 'error')
            return redirect_back_to_list()
    elif new_name:
        attribute = db.session.query(attribute_class) \
            .filter(func.lower(attribute_class.name) == new_name.lower()) \
            .order_by(attribute_class.id).first()
        if not attribute:
            attribute = create(new_name) if create else attribute_class(name=new_name)
            db.session.add(attribute)
            db.session.flush()
            flash(f"Created {noun} {attribute}.", 'success')
    else:
        flash(f"Choose a {noun} to add.", 'error')
        return redirect_back_to_list()

    bulk_datetime = datetime.utcnow()
    assets: list[Asset] = get_asset_list_from_request_args()
    assets_to_change = [asset for asset in assets if attribute not in getattr(asset, relationship)]
    for asset in assets_to_change:
        getattr(asset, relationship).append(attribute)
        db.session.add(asset)
        log(LogEvent.Update, object=asset, user=current_user, is_bulk=True,
            bulk_datetime=bulk_datetime.isoformat(), **{f'added_{noun}_id': attribute.id})
    attribute.last_used = datetime.now()
    db.session.add(attribute)
    db.session.commit()

    message = f"Given {len(assets_to_change)} assets the {noun} {attribute}."
    already_had = len(assets) - len(assets_to_change)
    if already_had:
        message += f" {already_had} already had it."
    flash(message, 'success')

    return redirect_back_to_list()
