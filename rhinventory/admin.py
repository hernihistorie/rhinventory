
import datetime
import os
import os.path

from flask import request, flash, redirect, url_for, current_app
from flask_login import current_user, login_required
from flask_admin import expose
from flask_admin.helpers import get_redirect_target
from flask_admin.model.helpers import get_mdict_item_or_list
from flask_admin.contrib.sqla import ModelView
from flask_admin.contrib.fileadmin import FileAdmin
from flask_admin.form.fields import Select2Field
#from flask_admin.form.upload import FileUploadField
from wtforms import Form, RadioField, StringField, FileField
from wtforms.validators import InputRequired
from sqlalchemy import desc
from werkzeug.utils import secure_filename

from rhinventory.extensions import db, admin
from rhinventory.db import LogItem, Category, Medium, Location, log, Asset, User, Transaction, File, FileCategory

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

class AssetFileForm(Form):
	file = FileField("File")
	title = StringField("Title", render_kw={"placeholder": "Title"})
	category = Select2Field("Category", choices=[(el.name, el.name) for el in FileCategory])

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

	details_template = "admin/asset_details.html"

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
	
	# Overridden https://flask-admin.readthedocs.io/en/latest/_modules/flask_admin/model/base/#BaseModelView.details_view
	@expose('/details/')
	def details_view(self):
		return_url = get_redirect_target() or self.get_url('.index_view')

		id = get_mdict_item_or_list(request.args, 'id')
		if id is None:
			return redirect(return_url)

		model = self.get_one(id)

		if model is None:
			flash('Record does not exist.', 'error')
			return redirect(return_url)

		template = self.details_template

		asset_file_form = AssetFileForm()

		return self.render(template,
							model=model,
							details_columns=self._details_columns,
							get_value=self.get_detail_value,
							return_url=return_url,
							asset_file_form=asset_file_form)

	@expose('/attach_file/', methods=['POST'])
	def attach_file_view(self):
		id = get_mdict_item_or_list(request.args, 'id')
		model = self.get_one(id)

		form = AssetFileForm(request.form)

		if form.validate():
			file = request.files['file']
			filename = secure_filename(file.filename)
			directory = f'assets/{id}'
			os.makedirs(current_app.config['FILES_DIR'] + "/" + directory, exist_ok=True)
			filepath = f'{directory}/{filename}'
			file.save(current_app.config['FILES_DIR'] + "/" + filepath)

			category = form.category.data
			if category == 'unknown' and filename.split('.')[-1].lower() in ('jpg', 'jpeg', 'png', 'gif'):
				category = 'image'

			file_db = File(filepath=filepath, storage='files', primary=False, category=category,
				title=form.title.data, upload_date=datetime.datetime.now(), user_id=current_user.id,
				asset_id=id)

			db.session.add(file_db)
			db.session.commit()
			
			if file_db.is_image:
				file_db.make_thumbnail()
				db.session.add(file_db)
				db.session.commit()
			flash("File {} uploaded".format(filename), 'success')
		else:
			flash("Upload form validation failed: {}".format(form.errors), 'error')
		
		return redirect(url_for('.details_view', id=id))

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

class FileView(CustomModelView):
	can_view_details = True
	details_template = "admin/file_details.html"

	@expose('/make_thumbnail/', methods=['POST'])
	def make_thumbnail_view(self):
		id = get_mdict_item_or_list(request.args, 'id')
		model = self.get_one(id)

		model.make_thumbnail()
		db.session.add(model)
		db.session.commit()
		flash("Thumbnail created", 'success')
		return redirect(url_for("file.details_view", id=id))

def add_admin_views(app):
	admin.add_view(AssetView(Asset, db.session))

	for table in [Category, Location]:
		admin.add_view(CustomModelView(table, db.session))

	admin.add_view(MediumView(Medium, db.session))
	admin.add_view(TransactionView(Transaction, db.session))

	admin.add_view(FileView(File, db.session))
	
	path = os.path.join(os.path.dirname(__file__), app.config['FILES_DIR'])
	admin.add_view(FileAdmin(path, '/files/', name='File management'))

	for table in [User, LogItem]:
		admin.add_view(AdminModelView(table, db.session))
