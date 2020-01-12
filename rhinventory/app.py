from flask import Flask, render_template, flash, redirect, url_for, send_file
from jinja2 import StrictUndefined

from rhinventory.extensions import db, admin, debug_toolbar
from rhinventory.admin import add_admin_views

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
    
    return app

