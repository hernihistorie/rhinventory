from uuid import UUID

from flask import redirect, request, flash, url_for
from flask_admin import expose
from wtforms import Form, IntegerField, StringField, HiddenField
from wtforms.validators import InputRequired, Optional

from rhinventory.extensions import db
from rhinventory.admin_views.model_view import CustomModelView
from rhinventory.util import require_write_access
from rhinventory.forms import UUIDValidator
from rhinventory.models.aggregates.floppy_disk_capture import FloppyDiskCapture
from rhinventory.events.floppy_disk_captures import FloppyDiskCaptureReassigned
from rhinventory.event_store.event_store import event_store


class ReassignFloppyDiskCaptureForm(Form):
    capture_id = HiddenField('Capture ID', validators=[InputRequired(), UUIDValidator()])
    new_asset_id = IntegerField('New Asset ID', validators=[InputRequired(message="Please enter an asset ID.")])
    reason_given = StringField('Reason', validators=[Optional()])


class FloppyDiskCaptureView(CustomModelView):
    can_edit = False
    can_delete = False
    can_create = False
    column_list = ('id', 'asset_id', 'asset_id_source', 'dumped_at', 'directory_name', 'has_errors', 'filename_incorrect')
    column_default_sort = ('id', True)
    details_template = 'admin/floppy_disk_capture/details.html'

    @expose('/reassign_floppy_disk_capture/', methods=['POST'])
    @require_write_access
    def reassign_floppy_disk_capture(self):
        """Emit a FloppyDiskCaptureReassigned event to reassign a floppy disk capture to a different asset."""
        form = ReassignFloppyDiskCaptureForm(request.form)
        
        if not form.validate():
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"{field}: {error}", "danger")
            return redirect(request.referrer or url_for('.index_view'))
        
        capture_uuid = UUID(form.capture_id.data)
        
        # Verify the capture exists
        capture = db.session.query(FloppyDiskCapture).filter(FloppyDiskCapture.id == capture_uuid).first()
        if not capture:
            flash("Floppy disk capture not found.", "danger")
            return redirect(request.referrer or url_for('.index_view'))
        
        assert form.new_asset_id.data
        with event_store.event_session_for_current_user() as event_session:
            reassignment_event = FloppyDiskCaptureReassigned(
                floppy_disk_capture_id=capture_uuid,
                new_asset_id=form.new_asset_id.data,
                reason_given=form.reason_given.data or None
            )
            event_session.ingest(reassignment_event)
        
        flash(f"Floppy disk capture reassigned to asset {form.new_asset_id.data} successfully.", "success")
        
        return redirect(url_for('.details_view', id=form.capture_id.data))
