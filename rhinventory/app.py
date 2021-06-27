import os

from flask import Flask, Blueprint, render_template, flash, redirect, url_for, send_file, Response, abort, request, session, jsonify
from flask_login import current_user, login_required, login_user, logout_user
from jinja2 import StrictUndefined

from rhinventory.extensions import db, admin, debug_toolbar, github, login_manager
from rhinventory.admin import add_admin_views
from rhinventory.db import User, Asset, Location, log

from rhinventory.labels import make_barcode, make_label, make_asset_label

def create_app(config_object='rhinventory.config'):
    app = Flask(__name__.split('.')[0], template_folder='templates')
    app.config.from_object(config_object)

    db.init_app(app)
    admin.init_app(app)
    debug_toolbar.init_app(app)
    github.init_app(app)
    login_manager.init_app(app)
    
    files_blueprint = Blueprint('files', __name__, static_url_path='/files', static_folder=app.config['FILES_DIR'])
    app.register_blueprint(files_blueprint)

    add_admin_views(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)
    

    @github.access_token_getter
    def token_getter():
        if current_user.is_authenticated:
            return current_user.github_access_token


    @app.route('/github-callback')
    @github.authorized_handler
    def authorized(access_token):
        #next_url = request.args.get('next') or url_for('index')
        if access_token is None:
            return redirect(url_for('index'))
        
        github_user = github.get('/user', access_token=access_token)

        user = User.query.filter_by(github_id=github_user['id']).first()
        if user is None:
            user = User(github_id=github_user['id'])
            db.session.add(user)

        user.github_access_token = access_token
        user.github_login = github_user['login']

        db.session.commit()

        login_user(user)

        return redirect(url_for('index'))


    @app.route('/login/github')
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        
        return github.authorize()


    @app.route('/logout')
    def logout():
        logout_user()
        return redirect(url_for('index'))


    @app.route('/user')
    def user():
        return jsonify(github.get('/user'))


    @app.route('/')
    def index():
        current_user.read_access = True
        current_user.write_access = True
        current_user.admin = True
        return redirect('/admin')
    
    
    @login_required
    @app.route('/barcode/<text>')
    def barcode_endpoint(text):
        fp = make_barcode(text)
        return send_file(fp,
                        #as_attachment=True,
                        #attachment_filename='a_file.txt',
                        mimetype='image/svg+xml')
    
    @login_required
    @app.route('/label/asset/<int:asset_id>', defaults={'small': False})
    @app.route('/label/asset/<int:asset_id>-small', defaults={'small': True})
    def label_asset(asset_id, small=False):
        asset = Asset.query.get(asset_id)
        if not asset: abort(404)

        label_filename = make_asset_label(asset, small=small)

        return send_file(open(label_filename, 'rb'), mimetype='image/png')
    
    @login_required
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
    
    @login_required
    @app.route('/label/location/<int:location_id>')
    def label_location(location_id):
        location = Location.query.get(location_id)
        if not location: abort(404)

        id = f"RHL{location_id:04}"
        label_filename = make_label(id, "LOCATION", location.name)

        return send_file(open(label_filename, 'rb'), mimetype='image/png')
    
    return app

