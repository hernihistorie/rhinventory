from uuid import UUID

from flask_admin.form.fields import Select2Field
from wtforms import Form, RadioField, StringField, BooleanField, FileField, MultipleFileField, HiddenField, IntegerField
from wtforms.validators import ValidationError

from rhinventory.db import FileCategory
from rhinventory.models.enums import Privacy


class UUIDValidator:
    """Validates that the field contains a valid UUID string."""
    
    def __init__(self, message: str | None = None):
        self.message = message or "Invalid UUID format."
    
    def __call__(self, form, field):
        if field.data:
            try:
                UUID(field.data)
            except (ValueError, TypeError):
                raise ValidationError(self.message)

class FileForm(Form):
    files = MultipleFileField("Files")
    category = Select2Field("Category", choices=[(el.value, el.name) for el in FileCategory], coerce=int)
    privacy = Select2Field("Privacy", choices=[(el.value, el.name) for el in Privacy], coerce=int)
    batch_number = IntegerField("Batch number", render_kw={'readonly': True})
    auto_assign = BooleanField("Auto assign", render_kw={'checked':''})
    sort_by_filename = BooleanField("Sort uploads by filename", render_kw={'checked':''})

class DropzoneFileForm(Form):
    privacy = Select2Field("Privacy", choices=[(el.value, el.name) for el in Privacy], coerce=int)
    batch_number = IntegerField("Batch number", render_kw={'readonly': True})
    auto_assign = BooleanField("Auto assign", render_kw={'checked':''})

class FileAssignForm(Form):
    asset = Select2Field("asset", coerce=int)
