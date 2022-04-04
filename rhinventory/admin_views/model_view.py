from flask import request, flash, redirect, url_for, current_app, jsonify
from flask_login import current_user, login_required
from flask_admin.contrib.sqla import ModelView

from rhinventory.extensions import db, admin
from rhinventory.db import log

class CustomModelView(ModelView):
    form_excluded_columns = ['transactions']

    def is_accessible(self):
        return current_user.is_authenticated and current_user.read_access
    
    def inaccessible_callback(self, name, **kwargs):
        flash("You don't have permission to view this page.  Please log in.", "warning")
        return redirect(url_for('admin.index', next=request.full_path))

    def on_model_change(self, form, instance, is_created):
        if not is_created:
            log("Update", instance, user=current_user)
        else:
            db.session.add(instance)
            db.session.commit()
            log("Create", instance, user=current_user)