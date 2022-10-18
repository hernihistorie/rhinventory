import os
import os.path
import datetime
import hashlib
import multiprocessing as mp

from flask import request, flash, redirect, url_for, current_app, jsonify
from flask_login import current_user
from flask_admin import expose
from flask_admin.helpers import get_redirect_target
from flask_admin.model.helpers import get_mdict_item_or_list
from werkzeug.utils import secure_filename

from rhinventory.db import log, Asset, File, FileCategory, get_next_file_batch_number
from rhinventory.extensions import db, simple_eval
from rhinventory.forms import FileForm, FileAssignForm
from rhinventory.admin_views.model_view import CustomModelView

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
        else:
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
