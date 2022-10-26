from flask_admin.form.fields import Select2Field
from wtforms import Form, RadioField, StringField, BooleanField, FileField, MultipleFileField, HiddenField, IntegerField

from rhinventory.db import FileCategory

class FileForm(Form):
    files = MultipleFileField("Files")
    category = Select2Field("Category", choices=[(el.value, el.name) for el in FileCategory], coerce=int)
    batch_number = IntegerField("Batch number", render_kw={'readonly': True})
    auto_assign = BooleanField("Auto assign", render_kw={'checked':''})

class FileAssignForm(Form):
    asset = Select2Field("asset", coerce=int)
