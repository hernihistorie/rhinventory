from flask import Flask, render_template, flash, redirect, url_for, send_file, Response
from jinja2 import StrictUndefined

from rhinventory.extensions import db, admin, debug_toolbar
from rhinventory.admin import add_admin_views
from rhinventory.db import Asset

def create_app(config_object='rhinventory.config'):
    app = Flask(__name__.split('.')[0])
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
        from rhinventory.labels import make_barcode
        fp = make_barcode(text)
        return send_file(fp,
                        #as_attachment=True,
                        #attachment_filename='a_file.txt',
                        mimetype='image/svg+xml')
    
    @app.route('/label/<int:asset_id>')
    def label_endpoint(asset_id):
        from rhinventory.labels import make_label

        asset = Asset.query.get(asset_id)

        id = f"RH{asset_id:05}"
        label_filename = make_label(id, asset.custom_code, asset.name)

        #return Response(label, mimetype='image/svg+xml')
        return send_file(open(label_filename, 'rb'), mimetype='image/png')
    
    return app

