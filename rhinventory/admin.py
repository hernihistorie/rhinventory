from flask import request
from flask_login import current_user, login_required
from flask_admin.contrib.sqla import ModelView
from wtforms import RadioField
from sqlalchemy import desc

from rhinventory.extensions import db, admin
from rhinventory.db import LogItem, Category, Medium, Location, log, Asset, User, Transaction, File

class CustomModelView(ModelView):
    form_excluded_columns = ['transactions']

    def is_accessible(self):
        return current_user.is_authenticated and current_user.read_access

    def on_model_change(self, form, instance, is_created):
        if not is_created:
            log("Update", instance, user=current_user)
        else:
            db.session.add(instance)
            db.session.commit()
            log("Create", instance, user=current_user)

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
					.filter(Asset.category_id == instance.category.id, Asset.custom_code != None) \
					.order_by(desc(Asset.custom_code)).limit(1).scalar()

				if last_category_asset:
					instance.custom_code = int(last_category_asset.custom_code) + 1
				else:
					instance.custom_code = 1

		super().on_model_change(form, instance, is_created)

	def get_save_return_url(self, model=None, is_created=False):
		return self.get_url('.details_view', id=model.id)

class MediumView(CustomModelView):
	column_default_sort = ('name', True)

class TransactionView(CustomModelView):
	can_view_details = True
	column_default_sort = ('date', True)

	def create_form(self, obj=None):
		form = super(TransactionView, self).create_form()

		# second condition forces program to not overwrite data that has been
		# sent by user. If data has been sent, `form.assets.data` is already filled
		# with appropriate stuff and thus, you must not overwrite it
		if "asset_id" in request.args.keys() and len(form.assets.data) == 0:
			asset_query = self.session.query(Asset).filter(Asset.id == request.args["asset_id"]).one()
			form.assets.data = [asset_query]

		return form

def add_admin_views():
	admin.add_view(AssetView(Asset, db.session))

	for table in [Category, Location]:
		admin.add_view(CustomModelView(table, db.session))

	admin.add_view(MediumView(Medium, db.session))
	admin.add_view(TransactionView(Transaction, db.session))

	for table in [File, User, LogItem]:
		admin.add_view(AdminModelView(table, db.session))
