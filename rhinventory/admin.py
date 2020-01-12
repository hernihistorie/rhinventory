from flask_admin.contrib.sqla import ModelView

from rhinventory.extensions import db, admin
from rhinventory.db import tables, LogItem, log

class CustomModelView(ModelView):
    form_excluded_columns = ['transactions']
    def on_model_change(self, form, instance, is_created):
        if not is_created:
            log("Update", instance)
        else:
            db.session.add(instance)
            db.session.commit()
            log("Create", instance)

    #def is_accessible(self):
    #    return current_user.is_authenticated

def add_admin_views():
    for table in tables + [LogItem]:
        admin.add_view(CustomModelView(table, db.session))