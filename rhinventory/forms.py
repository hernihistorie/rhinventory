from uuid import UUID

from flask_admin.contrib.sqla.ajax import QueryAjaxModelLoader
from flask_admin.form.fields import Select2Field
from flask_admin.model.ajax import DEFAULT_PAGE_SIZE
from flask_admin.model.fields import AjaxSelectField
from sqlalchemy import or_
from wtforms import Form, RadioField, StringField, BooleanField, FileField, MultipleFileField, HiddenField, IntegerField, TextAreaField
from wtforms.validators import ValidationError

from rhinventory.db import Asset, FileCategory
from rhinventory.extensions import db
from rhinventory.files.hh_code import parse_asset_lookup
from rhinventory.models.enums import Privacy
from rhinventory.models.properties.properties import properties


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

class AssetLookupLoader(QueryAjaxModelLoader):
    """Finds assets by name, or by hh code or number, in which case that exact asset comes first."""

    def __init__(self, name: str):
        super().__init__(name, db.session, Asset, fields=['name'],
            placeholder="Search by name or hh code...", minimum_input_length=1)

    def get_one(self, pk):
        asset_id = parse_asset_lookup(str(pk))
        return super().get_one(asset_id) if asset_id else None

    def get_list(self, term, offset=0, limit=DEFAULT_PAGE_SIZE):
        term = (term or '').strip()
        query = self.get_query()
        matches_name = Asset.name.icontains(term, autoescape=True)

        if asset_id := parse_asset_lookup(term):
            query = query.filter(or_(matches_name, Asset.id == asset_id)).order_by(Asset.id != asset_id)
        else:
            query = query.filter(matches_name)

        return query.order_by(Asset.id.desc()).offset(offset).limit(limit).all()

asset_lookup_loader = AssetLookupLoader('asset')

class FileAssignForm(Form):
    asset_id = AjaxSelectField(asset_lookup_loader, "Asset")

class StatementForm(Form):
    subject_id = HiddenField("Subject ID")
    property_id = Select2Field("Property", choices=[(prop.id, prop.name) for prop in properties], validators=[UUIDValidator()])
    value = TextAreaField("Value")
