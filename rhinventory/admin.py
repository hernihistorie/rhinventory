import datetime
import os
import os.path
from math import ceil
import multiprocessing as mp
import hashlib

from flask import request, flash, redirect, url_for, current_app, jsonify
from flask_login import current_user, login_required
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.helpers import get_redirect_target
from flask_admin.model.helpers import get_mdict_item_or_list
from flask_admin.contrib.sqla import ModelView
from flask_admin.contrib.fileadmin import FileAdmin
#from flask_admin.form.upload import FileUploadField
from wtforms import RadioField
from wtforms.validators import InputRequired
from sqlalchemy import desc
from werkzeug.utils import secure_filename
from simpleeval import EvalWithCompoundTypes

from rhinventory.extensions import db, admin
from rhinventory.db import LogItem, Category, Medium, Location, log, Asset, User, Transaction, File, FileCategory, Party, get_next_file_batch_number
from rhinventory.forms import FileForm, FileAssignForm

simple_eval = EvalWithCompoundTypes()

class CustomIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        next = request.args.get('next')
        return self.render('admin/index.html', next=next)

admin._set_admin_index_view(CustomIndexView()) # XXX this is not great

class CustomModelView(ModelView):
    form_excluded_columns = ['transactions']

    def is_accessible(self):
        return current_user.is_authenticated and current_user.read_access
    
    def inaccessible_callback(self, name, **kwargs):
        flash("You don't have permission to view this page.  Please log in.", "warning")
        return redirect(url_for('admin.index', next=request.full_path))

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
        'category.name',
        'medium.name',
        'name',
        'manufacturer',
        'parent.id',
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

    list_template = "admin/asset/list.html"
    details_template = "admin/asset/details.html"

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

    def _get_gallery_url(self, view_args):
        """
            Generate page URL with current page, sort column and
            other parameters.
            :param view:
                View name
            :param view_args:
                ViewArgs object with page number, filters, etc.
        """
        page = view_args.page or None
        desc = 1 if view_args.sort_desc else None

        kwargs = dict(page=page, sort=view_args.sort, desc=desc, search=view_args.search)
        kwargs.update(view_args.extra_args)

        if view_args.page_size:
            kwargs['page_size'] = view_args.page_size

        kwargs.update(self._get_filters(view_args.filters))

        return self.get_url('.gallery_view', **kwargs)

    @expose('/gallery/')
    def gallery_view(self):
        """
            List view
        """
        if self.can_delete:
            delete_form = self.delete_form()
        else:
            delete_form = None

        # Grab parameters from URL
        view_args = self._get_list_extra_args()

        # Map column index to column name
        sort_column = self._get_column_by_idx(view_args.sort)
        if sort_column is not None:
            sort_column = sort_column[0]

        # Get page size
        page_size = view_args.page_size or self.page_size

        # Get count and data
        count, data = self.get_list(view_args.page, sort_column, view_args.sort_desc,
                                    view_args.search, view_args.filters, page_size=page_size)

        list_forms = {}
        if self.column_editable_list:
            for row in data:
                list_forms[self.get_pk_value(row)] = self.list_form(obj=row)

        # Calculate number of pages
        if count is not None and page_size:
            num_pages = int(ceil(count / float(page_size)))
        elif not page_size:
            num_pages = 0  # hide pager for unlimited page_size
        else:
            num_pages = None  # use simple pager

        # Various URL generation helpers
        def pager_url(p):
            # Do not add page number if it is first page
            if p == 0:
                p = None

            return self._get_gallery_url(view_args.clone(page=p))

        def sort_url(column, invert=False, desc=None):
            if not desc and invert and not view_args.sort_desc:
                desc = 1

            return self._get_gallery_url(view_args.clone(sort=column, sort_desc=desc))

        def page_size_url(s):
            if not s:
                s = self.page_size

            return self._get_gallery_url(view_args.clone(page_size=s))

        # Actions
        actions, actions_confirmation = self.get_actions_list()
        if actions:
            action_form = self.action_form()
        else:
            action_form = None

        clear_search_url = self._get_gallery_url(view_args.clone(page=0,
                                                              sort=view_args.sort,
                                                              sort_desc=view_args.sort_desc,
                                                              search=None,
                                                              filters=None))

        return self.render(
            'admin/asset/gallery.html',
            data=data,
            list_forms=list_forms,
            delete_form=delete_form,
            action_form=action_form,

            # List
            list_columns=self._list_columns,
            sortable_columns=self._sortable_columns,
            editable_columns=self.column_editable_list,
            list_row_actions=self.get_list_row_actions(),

            # Pagination
            count=count,
            pager_url=pager_url,
            num_pages=num_pages,
            can_set_page_size=self.can_set_page_size,
            page_size_url=page_size_url,
            page=view_args.page,
            page_size=page_size,
            default_page_size=self.page_size,

            # Sorting
            sort_column=view_args.sort,
            sort_desc=view_args.sort_desc,
            sort_url=sort_url,

            # Search
            search_supported=self._search_supported,
            clear_search_url=clear_search_url,
            search=view_args.search,
            search_placeholder=self.search_placeholder(),

            # Filters
            filters=self._filters,
            filter_groups=self._get_filter_groups(),
            active_filters=view_args.filters,
            filter_args=self._get_filters(view_args.filters),

            # Actions
            actions=actions,
            actions_confirmation=actions_confirmation,

            # Misc
            enumerate=enumerate,
            get_pk_value=self.get_pk_value,
            get_value=self.get_list_value,
            return_url=self._get_gallery_url(view_args),

            extra_args={}
        )
    
    # Overridden https://flask-admin.readthedocs.io/en/latest/_modules/flask_admin/model/base/#BaseModelView.details_view
    @expose('/details/')
    def details_view(self):
        return_url = get_redirect_target() or self.get_url('.index_view')

        id = get_mdict_item_or_list(request.args, 'id')
        if id is None:
            return redirect(return_url)
        
        if id.startswith("RH"):
            id = id[2:]

        model = self.get_one(id)

        if model is None:
            flash('Record does not exist.', 'error')
            return redirect(return_url)

        template = self.details_template

        batch_number = get_next_file_batch_number()
        file_form = FileForm(batch_number=batch_number)

        return self.render(template,
                            model=model,
                            details_columns=self._details_columns,
                            get_value=self.get_detail_value,
                            return_url=return_url,
                            file_form=file_form)

class MediumView(CustomModelView):
    column_default_sort = ('name', True)

class TransactionView(CustomModelView):
    can_view_details = True
    column_default_sort = ('id', True)
    column_list = ('id', 'date', 'transaction_type', 'counterparty', 'assets')

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
    list_template = "admin/file/list.html"
    details_template = "admin/file/details.html"

    column_list = ('id', 'category', 'filepath', 'primary', 'asset', 'transaction', 'upload_date')
    form_excluded_columns = ('user', 'filepath', 'storage', 'has_thumbnail', 'analyzed', 'md5', 'original_md5', 'sha256', 'original_sha256', 'upload_date')
    column_default_sort = ('id', True)

    # Overridden https://flask-admin.readthedocs.io/en/latest/_modules/flask_admin/model/base/#BaseModelView.details_view
    @expose('/details/', methods=['GET', 'POST'])
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

        file_assign_form = FileAssignForm()
        assets = [(0, "No asset")]
        assets += [(a.id, str(a)) for a in self.session.query(Asset).order_by(Asset.id.asc())]
        file_assign_form.asset.choices = assets
        file_assign_form.asset.default = model.asset_id or 0
        file_assign_form.process(request.form)

        if request.method == "POST" and file_assign_form.validate():
            model.assign(file_assign_form.asset.data)
            db.session.add(model)
            log("Update", model, user=current_user)
            db.session.commit()
            flash(f"File assigned to asset #{file_assign_form.asset.data}", 'success')
            return redirect(url_for('.details_view', id=id))

        return self.render(template,
                            model=model,
                            details_columns=self._details_columns,
                            get_value=self.get_detail_value,
                            return_url=return_url,
                            file_assign_form=file_assign_form)

    @expose('/upload/', methods=['GET', 'POST'])
    def upload_view(self):
        id = get_mdict_item_or_list(request.args, 'id')
        if id:
            assign_asset = db.session.query(Asset).get(id)
        else:
            assign_asset = None

        batch_number = get_next_file_batch_number()

        form = FileForm(request.form, batch_number=batch_number)
        if request.method == 'POST' and form.validate():
            files = []
            image_files = []
            num_files = len(request.files.getlist("files"))
            print(f"Saving {num_files} files...")

            file_list = request.files.getlist("files")
            file_list.sort(key=lambda f: f.filename)

            duplicate_files = []

            for i, file in enumerate(file_list):
                # Calculate MD5 hash first to ensure file is not a dupe
                md5 = hashlib.md5(file.read()).digest()
                file.seek(0)

                matching_file = db.session.query(File).filter((File.md5 == md5) | (File.original_md5 == md5)).first()
                if matching_file:
                    duplicate_files.append((file.filename, matching_file))
                    continue

                # Save the file, partially accounting for filename collisions
                files_dir = current_app.config['FILES_DIR']
                filename = secure_filename(file.filename)
                directory = 'uploads'
                os.makedirs(files_dir + "/" + directory, exist_ok=True)
                filepath = f'{directory}/{filename}'
                while os.path.exists(os.path.join(files_dir, filepath)):
                    p = filepath.split('.')
                    p[-2] += '_1'
                    filepath = '.'.join(p)
                file.save(files_dir + "/" + filepath)

                category = FileCategory(form.category.data)
                if category == FileCategory.unknown and filename.split('.')[-1].lower() in ('jpg', 'jpeg', 'png', 'gif'):
                    category = FileCategory.image

                file_db = File(filepath=filepath, storage='files', primary=False, category=category,
                    md5=md5, batch_number=form.batch_number.data,
                    upload_date=datetime.datetime.now(), user_id=current_user.id)
                
                if file_db.is_image:
                    image_files.append(file_db)
                
                files.append(file_db)
            
            pool = mp.Pool(mp.cpu_count())

            if assign_asset:
                for file in files:
                    file.assign(assign_asset.id)
            else:
                print("Reading barcodes...")
                # Read barcodes in parallel
                if form.auto_assign.data and image_files:
                    result_objects = [pool.apply_async(File.read_rh_barcode, args=(file,)) for file in image_files]
                    asset_ids = [r.get() for r in result_objects]
                    for file, asset_id in zip(image_files, asset_ids):
                        file.assign(asset_id)

            print("Creating thumbnails...")
            # Create thumbnails in parallel
            if image_files:
                result_objects = [pool.apply_async(File.make_thumbnail, args=(file,)) for file in image_files]
                for file in image_files:
                    file.has_thumbnail = True
            
            pool.close()
            pool.join()

            print("Committing...")
            db.session.add_all(files)
            db.session.commit()

            for file in files:
                log("Create", file, user=current_user)
            db.session.commit()

            if assign_asset:
                flash(f"{len(files)} files uploaded and attached to asset", 'success')
                if duplicate_files:
                    flash(f"{len(files)} files skipped as duplicates", 'warning')
                return redirect(url_for("asset.details_view", id=assign_asset.id))
            else:
                if request.form.get('xhr', False):
                    return jsonify(files=[f.id for f in files],
                            duplicate_files=[(f0, f1.id) for f0, f1 in duplicate_files],
                            num_files=num_files,
                            auto_assign=form.auto_assign.data)
                else:
                    return redirect(url_for("file.upload_result_view", files=repr([f.id for f in files]),
                                duplicate_files=repr([(f0, f1.id) for f0, f1 in duplicate_files]),
                                auto_assign=form.auto_assign.data))
        return self.render('admin/file/upload.html', form=form)
    
    @expose('/upload/result', methods=['GET'])
    def upload_result_view(self):
        files = []
        for file_id in simple_eval.eval(request.args['files']):
            files.append(db.session.query(File).get(file_id))
        
        duplicate_files = []
        for f0, f1_id in simple_eval.eval(request.args['duplicate_files']):
            duplicate_files.append((f0, db.session.query(File).get(f1_id)))
        
        auto_assign = simple_eval.eval(request.args['auto_assign'])
        
        return self.render('admin/file/upload_result.html', files=files, duplicate_files=duplicate_files, auto_assign=auto_assign)


    @expose('/make_thumbnail/', methods=['POST'])
    def make_thumbnail_view(self):
        id = get_mdict_item_or_list(request.args, 'id')
        model = self.get_one(id)

        model.make_thumbnail()
        db.session.add(model)
        log("Update", model, user=current_user)
        db.session.commit()
        flash("Thumbnail created", 'success')
        return redirect(url_for("file.details_view", id=id))
    
    @expose('/rotate/', methods=['POST'])
    def rotate_view(self):
        id = get_mdict_item_or_list(request.args, 'id')
        model = self.get_one(id)

        if model.filename.lower().split('.')[-1] not in ('jpg', 'jpeg'):
            flash("Sorry, rotation is currently only available for JPEG files.", 'error')
            return redirect(url_for("file.details_view", id=id))
        
        rotation = get_mdict_item_or_list(request.args, 'rotation')

        model.rotate(int(rotation))
        db.session.add(model)
        log("Update", model, user=current_user, action="rotate", rotation=rotation)
        db.session.commit()
        flash("Image rotated", 'success')
        
        if request.args.get('refresh', False):
            return 'OK', 200, {'HX-Refresh': 'true'}

        return redirect(url_for("file.details_view", id=id))
    
    @expose('/assign/', methods=['POST'])
    def assign_view(self):
        id = get_mdict_item_or_list(request.args, 'id')
        model = self.get_one(id)

        asset_id = get_mdict_item_or_list(request.args, 'asset_id')

        model.assign(asset_id)
        db.session.add(model)
        log("Update", model, user=current_user)
        db.session.commit()

        flash(f"File assigned to asset #{asset_id}", 'success')
        if request.args.get('refresh', False):
            return 'OK', 200, {'HX-Refresh': 'true'}
        
        return redirect(url_for('.details_view', id=id))
    
    @expose('/auto_assign/', methods=['POST'])
    def auto_assign_view(self):
        id = get_mdict_item_or_list(request.args, 'id')
        model = self.get_one(id)

        asset_id = model.auto_assign()
        if asset_id:
            db.session.add(model)
            log("Update", model, user=current_user)
            db.session.commit()
            flash(f"Automatically assigned to asset #{asset_id:05}", 'success')
        else:
            flash("No RH barcode found.", 'success')
        return redirect(url_for("file.details_view", id=id))


class UserView(CustomModelView):
    column_list = ('id', 'username', 'github_login', 'read_access', 'write_access', 'admin')
    form_excluded_columns = ()
    column_default_sort = ('id', False)




def add_admin_views(app):
    admin.add_view(AssetView(Asset, db.session))

    for table in [Category, Location]:
        admin.add_view(CustomModelView(table, db.session))

    admin.add_view(MediumView(Medium, db.session))
    admin.add_view(TransactionView(Transaction, db.session))

    admin.add_view(AdminModelView(Party, db.session))

    admin.add_view(FileView(File, db.session))

    admin.add_view(UserView(User, db.session))
    
    #path = os.path.join(os.path.dirname(__file__), app.config['FILES_DIR'])
    #admin.add_view(FileAdmin(path, '/files/', name='File management'))

    for table in [LogItem]:
        admin.add_view(AdminModelView(table, db.session))
