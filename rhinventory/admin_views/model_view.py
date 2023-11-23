from flask import request, flash, redirect, url_for, current_app, jsonify
from flask_login import current_user, login_required
from flask_admin.contrib.sqla import ModelView

from rhinventory.extensions import db, admin
from rhinventory.db import log

class CustomModelView(ModelView):
    form_excluded_columns = ['transactions']

    @property
    def _write_access_acl(self):
        return current_user.is_authenticated and current_user.write_access
    
    can_edit = _write_access_acl
    can_create = _write_access_acl
    can_delete = _write_access_acl

    def is_accessible(self):
        return current_user.is_authenticated and current_user.read_access
    
    def inaccessible_callback(self, name, **kwargs):
        flash("You don't have permission to view this page.  Please log in.", "warning")
        return redirect(url_for('admin.index', next=request.full_path))

class AdminModelView(CustomModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.admin