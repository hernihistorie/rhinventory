"""Labels for the label printers, and the barcodes on them.

These don't need a login, as hhprint fetches labels without one (see user/hhprint.py).
"""
from flask import Blueprint, Response, abort, render_template, request, send_file
from simpleeval import EvalWithCompoundTypes

from rhinventory.db import Asset, Location
from rhinventory.extensions import db
from rhinventory.labels.labels import (
    LabelContent, asset_label_content, label_html, location_label_content, make_barcode, parse_label_variant,
    render_label,
)

labels_bp = Blueprint('labels', __name__, template_folder='templates')

simple_eval = EvalWithCompoundTypes()


def label_response(content: LabelContent, variant: str) -> Response:
    """The label as a PNG, or with ?format=html, the page it's rendered from."""
    try:
        size, logo = parse_label_variant(variant)
    except ValueError:
        abort(404)

    if request.args.get('format') == 'html':
        return Response(label_html(content, size, logo), mimetype='text/html')
    return Response(render_label(content, size, logo), mimetype='image/png')


@labels_bp.route('/barcode/<text>')
def barcode(text: str) -> Response:
    return send_file(make_barcode(text), mimetype='image/svg+xml')


# Variants are how hhprint asks for labels, e.g. /label/asset/3175-small-ha
@labels_bp.route('/label/asset/<int:asset_id>', defaults={'variant': ''})
@labels_bp.route('/label/asset/<int:asset_id>-<variant>')
def asset(asset_id: int, variant: str) -> Response:
    asset = db.session.get(Asset, asset_id)
    if not asset: abort(404)

    return label_response(asset_label_content(asset), variant)


@labels_bp.route('/label/assets')
def assets() -> str:
    """A page of labels to print on paper."""
    asset_ids = simple_eval.eval(request.args['asset_ids'])
    assets = Asset.query.filter(Asset.id.in_(asset_ids)).all()

    return render_template('labels/sheet.html', assets=assets)


@labels_bp.route('/label/location/<int:location_id>')
def location(location_id: int) -> Response:
    location = db.session.get(Location, location_id)
    if not location: abort(404)

    return label_response(location_label_content(location_id, location.name), '')
