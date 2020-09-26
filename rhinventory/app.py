import os

from flask import Flask, render_template, flash, redirect, url_for, send_file, Response, abort
from jinja2 import StrictUndefined

from rhinventory.extensions import db, admin, debug_toolbar
from rhinventory.admin import add_admin_views
from rhinventory.db import Asset, Location, log

from rhinventory.labels import make_barcode, make_label, make_asset_label

def create_app(config_object='rhinventory.config'):
    app = Flask(__name__.split('.')[0], template_folder='templates')
    app.config.from_object(config_object)

    db.init_app(app)
    admin.init_app(app)
    debug_toolbar.init_app(app)
    
    add_admin_views()

    @app.route('/')
    def index():
        return redirect('/admin')
    
    @app.route('/barcode/<text>')
    def barcode_endpoint(text):
        fp = make_barcode(text)
        return send_file(fp,
                        #as_attachment=True,
                        #attachment_filename='a_file.txt',
                        mimetype='image/svg+xml')
    
    @app.route('/label/asset/<int:asset_id>', defaults={'small': False})
    @app.route('/label/asset/<int:asset_id>-small', defaults={'small': True})
    def label_asset(asset_id, small=False):
        asset = Asset.query.get(asset_id)
        if not asset: abort(404)

        label_filename = make_asset_label(asset, small=small)

        return send_file(open(label_filename, 'rb'), mimetype='image/png')
    
    @app.route('/label/asset/<int:asset_id>/print', methods=['POST'], defaults={'small': False})
    @app.route('/label/asset/<int:asset_id>-small/print', methods=['POST'], defaults={'small': True})
    def print_label_asset(asset_id, small=False):
        asset = Asset.query.get(asset_id)
        if not asset: abort(404)

        label_filename = make_asset_label(asset, small=small)

        exit_code = os.system(f"brother_ql -p /dev/usb/lp0 -m QL-700 print -l 62 {label_filename}")

        if exit_code == 0:
            log("Other", asset, log_object=False, action="print_label", small=small)
            db.session.commit()
            
            return 'OK'
        else:
            return f'Error {exit_code}'
    
    @app.route('/label/location/<int:location_id>')
    def label_location(location_id):
        location = Location.query.get(location_id)
        if not location: abort(404)

        id = f"RHL{location_id:04}"
        label_filename = make_label(id, "LOCATION", location.name)

        return send_file(open(label_filename, 'rb'), mimetype='image/png')
    
    return app

