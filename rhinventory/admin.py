from flask_admin.contrib.sqla import ModelView
from wtforms import RadioField

from rhinventory.extensions import db, admin
from rhinventory.db import tables, LogItem, log, Asset

class CustomModelView(ModelView):
    form_excluded_columns = ['transactions']
    def on_model_change(self, form, instance, is_created):
        if not is_created:
            log("Update", instance)
        else:
            db.session.add(instance)
            db.session.commit()
            log("Create", instance)
    #def is_accessible(self):
    #    return current_user.is_authenticated

class RatingField(RadioField):
	def __init__(self, **kwargs):
		super().__init__(render_kw={'class': 'star-field'}, **kwargs)
		self.choices = [(0, 'unknown'), (1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')]

class AssetView(ModelView):
	form_overrides = {
		'condition': RatingField,
		'functionality': RatingField,
	}
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
		'name',
		'manufacturer',
		'custom_code',
		'note',
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
		'custom_code',
		'note',
		'serial',
		'condition',
		'functionality',
		'status',
		'parent',
	]

def add_admin_views():
    for table in tables + [LogItem]:
        admin.add_view(CustomModelView(table, db.session))
        
admin.add_view(AssetView(Asset, db.session))
