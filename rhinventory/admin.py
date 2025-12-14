import datetime

from flask import request, flash, redirect, url_for, current_app, jsonify
from flask_login import current_user, login_required
from flask_admin import Admin, AdminIndexView, expose
#from flask_admin.form.upload import FileUploadField

from rhinventory.extensions import db, admin, simple_eval
from rhinventory.db import DBEvent, LogItem, Medium, Location, Organization, log, LogItem, Asset, User, Transaction, File, Party
from rhinventory.models.aggregates.floppy_disk_capture import FloppyDiskCapture
from rhinventory.models.asset_attributes import AssetTag, Company, CompanyAlias, Packaging
from rhinventory.admin_views import CustomModelView, AdminModelView, AssetView, TransactionView, FileView
from rhinventory.admin_views.floppy_disk_capture import FloppyDiskCaptureView
from rhinventory.models.label_printer import LabelPrinter
from rhinventory.admin_views.magdb import add_magdb_views
from rhinventory.events.event import TestingEvent
from rhinventory.event_store.event_store import event_store

class CustomIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        # plot_script, plot_div = figure_counter(
        #     db.session,
        #     LogItem.id,
        #     LogItem.datetime,
        #     LogItem.table == "Asset" and LogItem.event == "Create",
        #     ['year', 'month', 'day'],
        #     lambda x: datetime.datetime(int(x.year), int(x.month), int(x.day)),
        #     count_total=True,
        #     title='Total assets')

        next = request.args.get('next')

        featured_tags = db.session.query(AssetTag).filter(AssetTag.is_featured == True).all()

        return self.render('admin/index.html',  featured_tags=featured_tags, next=next)

admin._set_admin_index_view(CustomIndexView()) # XXX this is not great

class MediumView(CustomModelView):
    column_default_sort = ('name', True)

class UserView(AdminModelView):
    column_list = ('id', 'organization', 'username', 'github_login', 'read_access', 'write_access', 'admin')
    form_excluded_columns = ('github_access_token', 'files', 'admin')
    column_default_sort = ('id', False)

    def is_accessible(self):
        return current_user.is_authenticated and current_user.admin

class EventView(CustomModelView):
    column_list = ('id', 'namespace', 'class_name', 'timestamp', 'ingested_at', 'event_session_id', 'event_session.application_name', 'event_session.user', 'event_session.push_key.authorized_by_user')
    column_details_list = ('id', 'namespace', 'class_name', 'timestamp', 'ingested_at', 'event_session_id', 'event_session.application_name', 'event_session.user', 'event_session.push_key.authorized_by_user', 'data')
    column_default_sort = ('ingested_at', False)
    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True

    details_template = 'admin/event/details.html'
    list_template = 'admin/event/list.html'

    @expose('/create_test_event/', methods=['POST'])
    def create_test_event(self):
        if not current_user.is_authenticated or not current_user.write_access:
            flash("You don't have permission to create test events.", "danger")
            return redirect(self.get_url('.index_view'))

        test_data = f"Test event created by {current_user.username or current_user.github_login} at {datetime.datetime.now()}"
        event = TestingEvent(test_data=test_data)
        
        with event_store.event_session_for_current_user() as event_session:
            event_session.ingest(event)

        flash(f"Test event created successfully with ID: {event.event_id}", "success")
        return redirect(self.get_url('.details_view', id=event.event_id))

def add_admin_views(admin):
    admin.add_view(AssetView(Asset, db.session))

    admin.add_view(TransactionView(Transaction, db.session))

    admin.add_view(FileView(File, db.session))

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