from flask_login import current_user, login_required
from flask_admin.contrib.sqla import ModelView
from wtforms import RadioField
from sqlalchemy import desc

from rhinventory.extensions import db, admin
from rhinventory.db import tables, LogItem, log, Asset, User

class CustomModelView(ModelView):
    form_excluded_columns = ['transactions']

    def is_accessible(self):
        return current_user.is_authenticated and current_user.read_access

    def on_model_change(self, form, instance, is_created):
        if not is_created:
            log("Update", instance)
        else:
            db.session.add(instance)
            db.session.commit()
            log("Create", instance)

class AdminModelView(CustomModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.admin

RATING_OPTIONS = [(0, 'unknown'), (1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')]
class RatingField(RadioField):
	def __init__(self, **kwargs):
		super().__init__(render_kw={'class': 'rating-field'}, **kwargs)
		self.choices = RATING_OPTIONS
		self.coerce = int
		self.default = 0

class AssetView(CustomModelView):
	form_overrides = {
		'condition': RatingField,
		'functionality': RatingField,
	}
	form_excluded_columns = ('metadata', 'logs', 'transactions')
	form_edit_rules = (
		'children',
		'location',
		'category',
		'custom_code',
		'medium',
		'name',
		'manufacturer',
		'model',
		'serial',
		'note',
		'condition',
		'functionality',
		'status',
		'parent',
	)
	form_create_rules = form_edit_rules

	can_view_details = True
	column_filters = [
		'location',
		'category',
	]
	column_searchable_list = [
		'name',
		'serial',
	]
	column_list = [
		'id',
		'location',
		'category',
		'custom_code',
		'medium',
		'name',
		'manufacturer',
		'serial',
		'condition',
		'functionality',
		'status',
		'parent',
	]
	column_sortable_list = [
		'id',
		'name',
		'manufacturer',
		'medium',
		'serial',
		'condition',
		'functionality',
		'status',
		'parent',
	]
	column_default_sort = ('id', True)
	column_choices = {
		'condition': RATING_OPTIONS,
		'functionality': RATING_OPTIONS,
	}
	can_export = True

	details_template = "admin/details.html"

	def on_model_change(self, form, instance, is_created):
		if is_created:
			if not instance.custom_code:
				last_category_asset = db.session.query(Asset) \
					.filter(Asset.category_id == instance.category.id) \
					.order_by(desc(Asset.custom_code)).limit(1).scalar()

				if last_category_asset:
					instance.custom_code = int(last_category_asset.custom_code) + 1
				else:
					instance.custom_code = 1

		super().on_model_change(form, instance, is_created)
	
	def get_save_return_url(self, model=None, is_created=False):
		return self.get_url('.details_view', id=model.id)

def add_admin_views():    
	admin.add_view(AssetView(Asset, db.session))

	for table in tables:
		admin.add_view(CustomModelView(table, db.session))

	for table in [User, LogItem]:
		admin.add_view(AdminModelView(table, db.session))
