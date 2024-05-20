from collections import defaultdict
from datetime import datetime
from enum import EnumMeta
import sys
from math import ceil
from typing import Optional, Union, Iterable

from flask import Response, redirect, request, flash, url_for, get_template_attribute
from wtforms import RadioField, TextAreaField, Field
import wtforms.validators
from flask_admin import expose
from flask_admin.helpers import get_redirect_target
from flask_admin.model.helpers import get_mdict_item_or_list
from flask_admin.form import Select2TagsField,  FormOpts
import flask_admin.form.rules as form_rules
from flask_admin.actions import action
from flask_admin.contrib.sqla import form
from flask_admin.helpers import get_form_data
from flask_login import current_user
from sqlalchemy import desc, nulls_last, func
from sqlalchemy.sql.functions import coalesce
from rhinventory.admin_views.utils import get_asset_list_from_request_args, visible_to_current_user

from rhinventory.extensions import db
from rhinventory.admin_views.model_view import CustomModelView
from rhinventory.db import Medium, Asset, get_next_file_batch_number, LogItem
from rhinventory.models.asset import AssetCondition
from rhinventory.models.enums import Privacy, PUBLIC_PRIVACIES
from rhinventory.models.file import IMAGE_CATEGORIES, File
from rhinventory.models.log import LogEvent, log
from rhinventory.forms import FileForm
from rhinventory.models.asset import AssetCategory
from rhinventory.models.asset_attributes import Company
from rhinventory.util import require_write_access

TESTING = "pytest" in sys.modules

class FixedRadioField(RadioField):
    _enum: EnumMeta
    def __init__(self, **kwargs):
        super().__init__(render_kw={'class': 'rating-field'}, **kwargs)
        self.choices = [(value.name, value.name) for value in self._enum]
        self.coerce = lambda x: x.split('.')[-1] if isinstance(x, str) else x.name
        self.validators = [wtforms.validators.Optional()]

class ConditionField(FixedRadioField):
    _enum = AssetCondition

class PrivacyField(FixedRadioField):
    _enum = Privacy

ALL_CATEGORIES = set(AssetCategory)
PRODUCT_ASSET_CATEGORIES = set([AssetCategory.game, AssetCategory.software, AssetCategory.multimedia,
            AssetCategory.rewritable_media, AssetCategory.literature, AssetCategory.console,
            AssetCategory.console_accesory, AssetCategory.computer,
            AssetCategory.computer_accessory, AssetCategory.computer_component,
            AssetCategory.keyboard, AssetCategory.computer_mouse, AssetCategory.television,
            AssetCategory.monitor])

def _last_used_query_factory_factory(cls: db.Model):
    return lambda: cls.query.order_by(
        nulls_last(cls.last_used.desc())
    )

class AssetView(CustomModelView):
    form_overrides: dict[str, type[Field]] = {
        'condition_new': ConditionField,
        'privacy': PrivacyField
#        'product_codes_new': Select2TagsField
    }
    form_excluded_columns = ('metadata', 'logs', 'transactions')
    form_columns = [
        'organization',
        'category',
#        'custom_code',
        'name',
#        'manufacturer',
        'companies',
#        'location',
        'hardware_type',
        'mediums',
        'packaging',
        'model',
        'product_codes',
        'serial',
        'condition_new',
#        'functionality',
#        'status',
        'note',
        'privacy',
        'tags',
        'privacy',
        'parent',
        'location',
        'contains',
#        'children',
    ]
    
    form_columns_categories: dict[str, Union[AssetCategory, Iterable[AssetCategory]]] = {
        'hardware_type': AssetCategory.computer_component,
        'mediums': [AssetCategory.game, AssetCategory.software, AssetCategory.multimedia,
            AssetCategory.rewritable_media],
        'model': PRODUCT_ASSET_CATEGORIES,
        'product_codes': PRODUCT_ASSET_CATEGORIES,
        'serial': PRODUCT_ASSET_CATEGORIES,
        'contains': AssetCategory.location,
        'parent': ALL_CATEGORIES - {AssetCategory.location}
    }
    form_ajax_refs = {
        'parent': {
            'fields': ('name', 'id'),
            'placeholder': '...',
            'page_size': 15,
            'minimum_input_length': 0,
        }
    }

    form_args = {
        'companies': {
            'query_factory': _last_used_query_factory_factory(Company)
        },
        'location': {
            'query_factory': lambda: Asset.query.filter(Asset.category == AssetCategory.location).order_by(
                Asset.name.asc()
            )
        },
        #'category': {
        #    'query_factory': lambda: Category.query.order_by(
        #        Category.id.asc()
        #    )
        #},
        #'medium': {
        #    'query_factory': lambda: sorted(
        #        Medium.query.order_by(Medium.name.asc()).all(),
        #        key=lambda m: m.name[0] in "0123456789"
        #    )
        #},
    }
    for last_used_attribute, class_ in Asset.LAST_USED_ATTRIBUTES.items():
        form_args[last_used_attribute] = {
            'query_factory': _last_used_query_factory_factory(class_)
        }

    can_view_details = True
    column_filters = [
        'organization.name',
        'category',
        'mediums.name',
        'packaging.name',
        'companies.name',
        'hardware_type.name',
        'files.category',
        'tags.name',
        'name',
        'manufacturer',
        'note',
        'parent.id',
        'privacy'
    ]
    column_searchable_list = [
        'id',
        'name',
        'serial',
    ]
    column_sortable_list = [
        'id',
        'name',
        'manufacturer',
        #'medium',
        'serial',
        'condition',
        'functionality',
        'status',
#        'parent',
    ]
    column_default_sort = ('id', True)
    column_choices = {
#        'condition': AssetCondition,
    }
    can_export = True
    page_size = 100

    list_template = "admin/asset/list.html"
    details_template = "admin/asset/details.html"
    edit_template = "admin/asset/edit.html"
    create_template = "admin/asset/create.html"

    def is_accessible(self):
        return True

    def on_model_change(self, form, instance: Asset, is_created):
        if is_created:
            if not instance.custom_code:
                instance.custom_code = Asset.get_free_custom_code(instance.category)
        
        super().on_model_change(form, instance, is_created)
    
    def after_model_change(self, form, model, is_created):
        for last_used_attribute in Asset.LAST_USED_ATTRIBUTES.keys():
            obj_list = getattr(model, last_used_attribute)
            if obj_list:
                for obj in obj_list:
                    obj.last_used = datetime.now()
                    db.session.add(obj)
        
        self.session.commit()

    # From https://stackoverflow.com/a/60829958
    def update_model(self, form, model: Asset):
        """
            Update model from form.
            :param form:
                Form instance
            :param model:
                Model instance
        """
        model_id = model.id
        try:

            old_category: AssetCategory = model.category
            new_category: AssetCategory = AssetCategory[form.category.data]

            if new_category != old_category:
                model.custom_code = Asset.get_free_custom_code(new_category)
            
            # continue processing the form

            form.populate_obj(model)
            self._on_model_change(form, model, False)
            self.session.commit()
            # Since we may have changed the category, we have to query
            # for the model anew 
            model = db.session.query(Asset).get(model_id)
        except Exception as ex:
            if not self.handle_view_exception(ex):
                flash('Failed to update record. ' + str(ex), 'error')
                #log.exception('Failed to update record.')

            self.session.rollback()

            return False
        else:
            if new_category != old_category:
                flash(f"Category of asset updated - {model}.", 'success')

            self.after_model_change(form, model, False)
        
        return True

    def get_save_return_url(self, model=None, is_created=False):
        if '_save_and_print' in request.form:
            return self.get_url('.details_view', id=model.id, print=1)
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

    def get_list_value(context, model, column):
        if not visible_to_current_user(model):
            if column == "name":
                return "(skrytý předmět)"
            return ""
        
        if column == "flags":
            return get_template_attribute("admin/asset/_macros.html", "render_flags")(model)
        elif column == "name":
            return get_template_attribute("admin/asset/_macros.html", "render_name_column")(model)
        elif column == "code":
            return get_template_attribute("admin/asset/_macros.html", "render_code_column")(model)
        else:
            return super().get_list_value(context, model, column)

    def get_list_columns(self):
        return [
            ('id', 'ID'),
            ('code', 'Code'),
            ('name', 'Name'),
            ('flags', 'Flags'),
            #('location', 'Location'),
            #('category', 'Category'),
            #('custom_code', 'Custom Code'),
            #('medium', 'Medium'), ('hardware_type', 'Hardware Type'), ('name', 'Name'), ('manufacturer', 'Manufacturer'), ('serial', 'Serial'), ('parent', 'Parent'), ('transactions', 'Transactions')
        ]

    def _apply_search(self, query, count_query, joins, count_joins, search: str):
        if search.lower().startswith('rh') or search.lower().startswith('hh'):
            search_id = int(search[2:])
            query = query.filter(Asset.id == search_id)
            search = ""
        return super()._apply_search(query, count_query, joins, count_joins, search)

    def get_query(self):
        if current_user.is_authenticated and current_user.read_access:
            return self.session.query(self.model)
        else:
            return self.session.query(self.model).filter(Asset.privacy.in_(PUBLIC_PRIVACIES))
    
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
    @expose('/details/<int:id>')
    @expose('/details/<int:id>-<string:slug>')
    def details_view(self, id=None, slug=None):
        return_url = get_redirect_target() or self.get_url('.index_view')

        if id is not None:
            id = str(id)
        else:
            id = get_mdict_item_or_list(request.args, 'id')
        if id is None:
            return redirect(return_url)
        
        if id.startswith("RH"):
            id = id[2:]

        model: Asset = self.get_one(id)

        if model is None:
            flash('Record does not exist.', 'error')
            return redirect(return_url)
        
        if not visible_to_current_user(model):
            return self.render('admin/asset/private.html', model_id=model.id)

        template = self.details_template

        batch_number = get_next_file_batch_number()
        file_form = FileForm(batch_number=batch_number)

        logs = db.session.query(LogItem).filter(
            LogItem.table.startswith("Asset"), # XXX imperfect! This will also get "AssetTag" and similar
            LogItem.object_id == model.id
        ).order_by(LogItem.datetime.desc()).all()

        return self.render(template,
                            model=model,
                            details_columns=self._details_columns,
                            get_value=self.get_detail_value,
                            return_url=return_url,
                            file_form=file_form,
                            logs=logs,
                            AssetCategory=AssetCategory)
    
    @expose('/new2/', methods=['GET'])
    @require_write_access
    def new_view(self):
        return self.render('admin/asset/new.html')
    

    @expose('/map/', methods=['GET'])
    def map_view(self):
        if not current_user.is_authenticated:
            return self.inaccessible_callback(None)
        # This code brought to you by GPT-4

        # First, create a subquery that returns the count of files for each asset
        images_count_subquery = (
            db.session.query(File.asset_id, func.count(File.id).label("image_count"))
            .filter(File.category.in_(IMAGE_CATEGORIES))
            .group_by(File.asset_id)
            .subquery()
        )

        # Now, join the Asset table with the subquery and select all assets
        # along with the file count for each asset
        assets_with_image_count = (
            db.session.query(
                Asset, coalesce(images_count_subquery.c.image_count, 0).label("image_count")
            )
            .outerjoin(images_count_subquery, Asset.id == images_count_subquery.c.asset_id)
            .all()
        )

        image_count_by_id: dict[int, int | None] = defaultdict(lambda: None)
        asset_by_id: dict[int, Asset | None] = defaultdict(lambda: None)
        max_id: int = 0

        assets_with_image = 0

        # assets_with_has_image will contain a list of tuples with the Asset object and the boolean value
        # You can unpack the tuple to get each asset and its "has_file" attribute, like this:
        for asset, image_count in assets_with_image_count:
            image_count_by_id[asset.id] = image_count
            asset_by_id[asset.id] = asset
            if image_count:
                assets_with_image += 1
            if max_id < asset.id:
                max_id = asset.id


        return self.render('admin/asset/map.html', image_count_by_id=image_count_by_id, asset_by_id=asset_by_id, max_id=max_id, assets_with_image_fraction=assets_with_image / len(assets_with_image_count))
                    
    

    @expose('/publicize/', methods=['GET', 'POST'])
    def publicize_view(self):
        start_id = int(request.args.get('start_id', 0))
        count = int(request.args.get('count', 50))
        if request.method != "POST":
            all_assets = db.session.query(Asset)
            private_implicit_assets = db.session.query(Asset)\
                .filter(Asset.privacy == Privacy.private_implicit)
            
            all_assets_count = all_assets.count()
            private_implicit_count = private_implicit_assets.count()
            assets = private_implicit_assets.filter(Asset.id >= start_id).order_by(Asset.id.asc()).limit(count).all()
        else:
            if '_skip' in request.form:
                return redirect(url_for('.publicize_view'))
            PRIVACY_DICT = {
                'public': Privacy.public,
                'private': Privacy.private,
                'default': Privacy.public
            }
            num_files_changed = 0
            num_assets_changed = 0
            for key, value in request.form.items():
                if key.startswith("file"):
                    file_id = int(key.split('-')[1])
                    file = db.session.query(File).filter(File.id == file_id).one()
                    if value == 'default' and '_publicize' not in request.form:
                        continue
                    file.privacy = PRIVACY_DICT[value]
                    db.session.add(file)
                    num_files_changed += 1
            
            for key, value in request.form.items():
                if key.startswith("asset"):
                    asset_id = int(key.split('-')[1])
                    asset = db.session.query(Asset).filter(Asset.id == asset_id).one()
                    if value == 'default' and '_publicize' not in request.form:
                        continue
                    asset.privacy = PRIVACY_DICT[value]
                    db.session.add(asset)
                    for file in asset.files:
                        if file.privacy == Privacy.private_implicit:
                            file.privacy = PRIVACY_DICT[value]
                            db.session.add(file)
                            num_files_changed += 1
                    num_assets_changed += 1
            db.session.commit()
            flash(f"Saved {num_assets_changed} assets and {num_files_changed} files.")
            return redirect(url_for('.publicize_view'))


        return self.render('admin/asset/publicize.html',
                           assets=assets,
                           all_assets_count=all_assets_count,
                           private_implicit_count=private_implicit_count,
                           count=count)
                    
    
    @action('create_transaction', 'Create transaction')
    @require_write_access
    def create_transaction(self, asset_ids):
        return redirect(url_for('transaction.create_view', asset_id=repr(asset_ids)))

    def get_form(self):
        return self.make_asset_form(self.category)

    def make_asset_form(self, category: AssetCategory, bulk=False):
        form_columns = []
        for var in self.form_columns:
            if var in self.form_columns_categories:
                form_column_categories = self.form_columns_categories[var]
                if not isinstance(form_column_categories, Iterable):
                    form_column_categories = [form_column_categories]
                if category not in form_column_categories:
                    continue
            form_columns.append(var)
        
        if bulk:
            self.form_overrides['name'] = TextAreaField

        converter = self.model_form_converter(self.session, self)
        form_class = form.get_form(self.model, converter,
                                  base_class=self.form_base_class,
                                  only=form_columns,
                                  exclude=self.form_excluded_columns,
                                  field_args=self.form_args,
                                  ignore_hidden=self.ignore_hidden,
                                  extra_fields=self.form_extra_fields)

        if bulk:
            del self.form_overrides['name']

        return form_class

    def create_form(self, obj=None, bulk=False):
        if "category" in request.args.keys():
            category = AssetCategory[request.args["category"]]
        else:
            category = AssetCategory.unknown
        
        #form = self._create_form_class(get_form_data(), obj=obj)
        form = self.make_asset_form(category, bulk=bulk)(get_form_data(), obj=obj)

        form.category.data = category.name

        if not form.organization.data:
            form.organization.data = current_user.organization

        if "parent_id" in request.args.keys() and not form.parent.data:
            form.parent.data = self.session.query(Asset).get(request.args["parent_id"])

        return form

    def edit_form(self, obj: Asset):
        form = self.make_asset_form(obj.category)(get_form_data(), obj=obj)
        return form

    @expose('/add_contents/', methods=['POST'])
    @require_write_access
    def add_contents_view(self):
        asset_id = int(request.form['asset_id'])
        asset: Asset
        asset = db.session.query(Asset).get(asset_id)
        assert asset

        num_assets = 0
        response = redirect(url_for('asset.details_view', id=asset_id))
        for rh_id in request.form['id_list'].lower().split():
            if not rh_id.strip():
                continue
            if not rh_id.startswith('rh'):
                flash(f"Error: Some ID doesn't start with 'rh': {rh_id}", 'error')
                return response
            
            try:
                contained_asset_id = int(rh_id[2:])
            except ValueError:
                flash(f"Error: Some ID not a number: {rh_id}", 'error')
                return response
                
            contained_asset: Asset
            contained_asset = db.session.query(Asset).get(contained_asset_id)
            if not contained_asset:
                flash(f"Error: Some ID doesn't correspond to an asset: {rh_id}", 'error')
                return response
            
            contained_asset.location_id_new = asset.id
            db.session.add(contained_asset)
            log("Update", contained_asset, user=current_user, assigned_location_asset_id=asset.id)
            num_assets += 1
        
        db.session.commit()
        flash(f"Added {num_assets} assets as contents.", "success")
        return response

    @expose('/set_parent_bulk/', methods=['POST'])
    @require_write_access
    def set_parent_bulk(self) -> Response:
        parent_asset_id = int(request.form['parent_asset_id'])
        parent_asset: Asset | None = db.session.query(Asset).get(parent_asset_id)
        if not parent_asset:
            flash(f"Asset with id {parent_asset_id} not found.", 'error')
            return redirect(url_for('.index_view'))
        
        assert isinstance(parent_asset, Asset)

        bulk_datetime = datetime.utcnow()
        assets: list[Asset] = get_asset_list_from_request_args()
        for asset in assets:
            asset.parent_id = parent_asset.id
            db.session.add(asset)
            log(LogEvent.Update, object=asset, user=current_user, is_bulk=True, bulk_datetime=bulk_datetime.isoformat())
        db.session.commit()

        message = f"Parent for {len(assets)} assets set to be {parent_asset}."

        flash(message, "success")

        return redirect(url_for('.index_view'))

    @expose('/bulk_new/', methods=('GET', 'POST'))
    @require_write_access
    def bulk_create_view(self):
        """
            Bulk create model view

            Based on .venv/lib/python3.11/site-packages/flask_admin/model/base.py#L2071
        """
        return_url = get_redirect_target() or self.get_url('.index_view')

        if not self.can_create:
            return redirect(return_url)

        form = self.create_form(bulk=True)

        if self.validate_form(form):
            names = form.name.data.split('\n')
            models = []
            for name in names:
                if not name.strip():
                    continue
                form.name.data = name.strip()
                models.append(self.create_model(form))
            if models:
                flash(f'{len(models)} records was successfully created.', 'success')
                return redirect(
                    self.get_url(endpoint='.index_view', selected=",".join(str(m.id) for m in models))
                )

        form_opts = FormOpts(widget_args=self.form_widget_args,
                             form_rules=self._form_create_rules)

        template = self.create_template

        return self.render(template,
                           form=form,
                           form_opts=form_opts,
                           return_url=return_url)

