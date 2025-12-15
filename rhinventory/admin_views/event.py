import datetime
from flask import redirect, flash
from flask_admin import expose
from flask_login import current_user

from rhinventory.admin_views.model_view import CustomModelView
from rhinventory.event_store.event_store import event_store
from rhinventory.events.events import TestingEvent

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
