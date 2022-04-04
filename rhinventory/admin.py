import datetime

from flask import request, flash, redirect, url_for, current_app, jsonify
from flask_login import current_user, login_required
from flask_admin import Admin, AdminIndexView, expose
#from flask_admin.form.upload import FileUploadField

from rhinventory.extensions import db, admin, simple_eval
from rhinventory.db import LogItem, Category, Medium, Location, Organization, log, LogItem, Asset, User, Transaction, File, Party
from rhinventory.admin_views import CustomModelView, AssetView, TransactionView, FileView
from rhinventory.util import figure_counter

class CustomIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        plot_script, plot_div = figure_counter(
            db.session,
            LogItem.id,
            LogItem.datetime,
            LogItem.table == "Asset" and LogItem.event == "Create",
            ['year', 'month', 'day'],
            lambda x: datetime.datetime(int(x.year), int(x.month), int(x.day)),
            count_total=True,
            title='Total assets')

        next = request.args.get('next')
        return self.render('admin/index.html', plot_script=plot_script, plot_div=plot_div, next=next)

admin._set_admin_index_view(CustomIndexView()) # XXX this is not great

class AdminModelView(CustomModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.admin

class CategoryView(CustomModelView):
    form_excluded_columns = ('assets')

class MediumView(CustomModelView):
    column_default_sort = ('name', True)

class UserView(CustomModelView):
    column_list = ('id', 'username', 'github_login', 'read_access', 'write_access', 'admin')
    form_excluded_columns = ()
    column_default_sort = ('id', False)


def add_admin_views(app):
    admin.add_view(AssetView(Asset, db.session))

    admin.add_view(CategoryView(Category, db.session))

    admin.add_view(CustomModelView(Location, db.session))

    admin.add_view(MediumView(Medium, db.session))
    admin.add_view(TransactionView(Transaction, db.session))

    admin.add_view(AdminModelView(Party, db.session))

    admin.add_view(AdminModelView(Organization, db.session))

    admin.add_view(FileView(File, db.session))

    admin.add_view(UserView(User, db.session))
    
    #path = os.path.join(os.path.dirname(__file__), app.config['FILES_DIR'])
    #admin.add_view(FileAdmin(path, '/files/', name='File management'))

    for table in [LogItem]:
        admin.add_view(AdminModelView(table, db.session))
