import datetime

from flask import request, flash, redirect, url_for, current_app, jsonify
from flask_login import current_user, login_required
from flask_admin import Admin, AdminIndexView, expose
#from flask_admin.form.upload import FileUploadField

from rhinventory.admin_views.event import EventView
from rhinventory.extensions import db, admin, simple_eval
from rhinventory.db import DBEvent, LogItem, Medium, Location, Organization, log, LogItem, Asset, User, Transaction, File, Party
from rhinventory.models.aggregates.floppy_disk_capture import FloppyDiskCapture
from rhinventory.models.aggregates.file import FileAggregate
from rhinventory.models.asset_attributes import AssetTag, Company, CompanyAlias, Packaging
from rhinventory.admin_views import CustomModelView, ReadOnlyCustomModelView, AdminModelView, AssetView, TransactionView, FileView
from rhinventory.admin_views.floppy_disk_capture import FloppyDiskCaptureView
from rhinventory.models.label_printer import LabelPrinter
from rhinventory.admin_views.magdb import add_magdb_views
from rhinventory.event_store.event_store import event_store

class CustomIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        import json as json_module
        from rhinventory.stats import get_stats_table, get_asset_chart_data, PERIOD_LABELS, CATEGORY_LABELS, EVENT_TYPE_LABELS

        next = request.args.get('next')

        featured_tags = db.session.query(AssetTag).filter(AssetTag.is_featured == True).all()

        stats = None
        asset_chart_data = None
        if current_user.is_authenticated and current_user.read_access:
            stats = get_stats_table()
            asset_chart_data = json_module.dumps(get_asset_chart_data())

        return self.render('admin/index.html', featured_tags=featured_tags, next=next, stats=stats, asset_chart_data=asset_chart_data,
            period_labels=PERIOD_LABELS, category_labels=CATEGORY_LABELS, event_type_labels=EVENT_TYPE_LABELS)

admin._set_admin_index_view(CustomIndexView()) # XXX this is not great

class MediumView(CustomModelView):
    column_default_sort = ('name', True)

class UserView(AdminModelView):
    column_list = ('id', 'organization', 'username', 'github_login', 'read_access', 'write_access', 'admin')
    form_excluded_columns = ('github_access_token', 'files', 'admin')
    column_default_sort = ('id', False)

    def is_accessible(self):
        return current_user.is_authenticated and current_user.admin

def add_admin_views(admin: Admin) -> None:
    admin.add_view(AssetView(Asset, db.session))

    admin.add_view(TransactionView(Transaction, db.session))

    admin.add_view(FileView(File, db.session))

    admin.add_view(ReadOnlyCustomModelView(FileAggregate, db.session, category="Misc"))

    admin.add_view(CustomModelView(Location, db.session, category="Misc"))

    admin.add_view(CustomModelView(Company, db.session, category="Misc"))
    
    admin.add_view(CustomModelView(CompanyAlias, db.session, category="Misc"))

    admin.add_view(MediumView(Medium, db.session, category="Misc"))

    admin.add_view(CustomModelView(Packaging, db.session, category="Misc"))

    class AssetTagView(CustomModelView):
        column_list = ('id', 'name', 'description', 'is_featured', 'is_collection', 'is_project', 'is_post', 'order')
        column_default_sort = ('id', True)
        details_template = 'admin/asset_tag/details.html'

    admin.add_view(AssetTagView(AssetTag, db.session, category="Misc"))

    admin.add_view(FloppyDiskCaptureView(FloppyDiskCapture, db.session, category="Misc"))

    admin.add_view(CustomModelView(Party, db.session, category="People"))

    admin.add_view(AdminModelView(Organization, db.session, category="People"))

    admin.add_view(UserView(User, db.session, category="Admin"))

    admin.add_view(CustomModelView(LabelPrinter, db.session, category="Admin"))

    admin.add_view(EventView(DBEvent, db.session, category="Admin"))
    
    #path = os.path.join(os.path.dirname(__file__), app.config['FILES_DIR'])
    #admin.add_view(FileAdmin(path, '/files/', name='File management'))

    for table in [LogItem]:
        admin.add_view(AdminModelView(table, db.session, category="Admin"))

    add_magdb_views(admin, db.session)