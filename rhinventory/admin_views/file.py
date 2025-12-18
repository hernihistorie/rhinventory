from io import BufferedReader, FileIO
import os
import os.path
import datetime
import hashlib
import multiprocessing as mp
from pathlib import Path
import random
import string

import blake3
from flask import abort, get_template_attribute, request, flash, redirect, url_for, current_app, jsonify
from flask_login import current_user
from flask_admin import expose
from flask_admin.helpers import get_redirect_target
from flask_admin.model.helpers import get_mdict_item_or_list
from werkzeug.datastructures.file_storage import FileStorage
from werkzeug.utils import secure_filename
from rhinventory.admin_views.utils import visible_to_current_user

from rhinventory.datatypes.hashes import BLAKE3Hash, Hashes, MD5Hash, SHA256Hash
from rhinventory.db import log, Asset, File, FileCategory, get_next_file_batch_number
from rhinventory.extensions import db, simple_eval
from rhinventory.files.utils import get_dropzone_path, get_dropzone_files
from rhinventory.forms import DropzoneFileForm, FileForm, FileAssignForm
from rhinventory.admin_views.model_view import CustomModelView
from rhinventory.models.file import FileStore
from rhinventory.models.enums import Privacy
from rhinventory.util import parse_hh_code, require_write_access


class DuplicateFile(RuntimeError):
    def __init__(self, message: str, matching_file: File):
        super().__init__(message)
        self.matching_file = matching_file


def calculate_file_hashes(file: BufferedReader | FileStorage) -> Hashes:
    """Calculate MD5, SHA256, and BLAKE3 hashes for a given file-like object."""
    hash_md5 = hashlib.md5()
    hash_sha256 = hashlib.sha256()
    hash_blake3 = blake3.blake3()

    file.seek(0)
    while chunk := file.read(8192):
        hash_md5.update(chunk)
        hash_sha256.update(chunk)
        hash_blake3.update(chunk)
    file.seek(0)

    hashes = Hashes(
        md5=MD5Hash(hash_md5.digest()),
        sha256=SHA256Hash(hash_sha256.digest()),
        blake3=BLAKE3Hash(hash_blake3.digest())
    )
    return hashes


def upload_file(file: FileStorage | Path, category: int | FileCategory=0, batch_number: int | None=None, privacy: int | Privacy=Privacy.private_implicit) -> File:
    """
    Handles file upload, check for duplicacy and save the file, but doesn't commit File object data to database.

    :param file: File handler.
    :param category: category of file, int from FileCategory
    :param batch_number:
    :param privacy: privacy setting, int from Privacy enum, defaults to private_implicit
    :return: object of type File, not committed to database.
    """
    if isinstance(file, Path):
        filename = file.name

        size = os.path.getsize(file)

        hashes = calculate_file_hashes(open(file, 'rb'))

    else:
        filename = file.filename
        assert filename
        size = file.content_length

        hashes = calculate_file_hashes(file)

    matching_file = db.session.query(File).filter(
            (File.md5 == hashes.md5) | (File.original_md5 == hashes.md5)
        ).filter(File.is_deleted == False).first()

    if matching_file:
        raise DuplicateFile("Duplicate file", matching_file)

    # Save the file, partially accounting for filename collisions
    file_store = FileStore(current_app.config['DEFAULT_FILE_STORE'])
    files_dir = current_app.config['FILE_STORE_LOCATIONS'][file_store.value]
    assert isinstance(files_dir, str)
    filename = secure_filename(filename)
    if not filename.strip():
        filename = str(datetime.datetime.now().timestamp()) + str(random.randint(0, 1000))
    directory = 'uploads'
    os.makedirs(files_dir + "/" + directory, exist_ok=True)
    filepath = f'{directory}/{filename}'
    while os.path.exists(os.path.join(files_dir, filepath)):
        p = filepath.split('.')
        if len(p) < 2:
            p[0] += '_1'
        else:
            p[-2] += '_1'
        filepath = '.'.join(p)

    if isinstance(file, FileStorage):
        file.save(files_dir + "/" + filepath)
    else:
        # move the file
        os.rename(file, files_dir + "/" + filepath)
    size = os.path.getsize(files_dir + "/" + filepath)

    if isinstance(category, int):
        category = FileCategory(category)
    if category == FileCategory.unknown and filename.split('.')[-1].lower() in ('jpg', 'jpeg', 'png', 'gif'):
        category = FileCategory.image

    if isinstance(privacy, int):
        privacy = Privacy(privacy)

    db_file = File()
    db_file.filepath = filepath
    db_file.storage = file_store
    db_file.primary = False
    db_file.category = category
    db_file.md5 = hashes.md5
    db_file.sha256 = hashes.sha256
    db_file.blake3 = hashes.blake3
    if batch_number:
        db_file.batch_number = batch_number
    db_file.upload_date = datetime.datetime.now()
    db_file.user_id = current_user.id
    db_file.size = size
    db_file.privacy = privacy
    return db_file

class FileView(CustomModelView):
    can_view_details = True
    list_template = "admin/file/list.html"
    details_template = "admin/file/details.html"

    column_list = ('id', 'category', 'filepath', 'primary', 'asset', 'transaction', 'upload_date')
    #form_excluded_columns = ('user', 'filepath', 'storage', 'has_thumbnail', 'analyzed', 'md5', 'original_md5', 'sha256', 'original_sha256', 'upload_date')
    form_excluded_columns = ['has_thumbnail', 'analyzed', 'md5', 'original_md5', 'sha256', 'original_sha256', 'blake3', 'upload_date']
    column_default_sort = ('id', True)

    column_searchable_list = [
        'filepath',
        'asset.name',
        'md5',
    ]

    def is_accessible(self):
        return True

    # Overridden https://flask-admin.readthedocs.io/en/latest/_modules/flask_admin/model/base/#BaseModelView.details_view
    @expose('/details/', methods=['GET', 'POST'])
    def details_view(self):
        return_url = get_redirect_target() or self.get_url('.index_view')

        id = get_mdict_item_or_list(request.args, 'id')
        if id is None:
            return redirect(return_url)

        model: File | None = self.get_one(id)

        if model is None:
            flash('Record does not exist.', 'error')
            return redirect(return_url)
        
        assert isinstance(model, File)
        
        if not visible_to_current_user(model):
            flash('You do not have permission to view this file.', 'error')
            return redirect('/')

        template = self.details_template

        file_assign_form = FileAssignForm()
        assets = [(0, "No asset")]
        #assets += [(a.id, str(a)) for a in self.session.query(Asset).order_by(Asset.id.asc())]
        file_assign_form.asset.choices = assets
        file_assign_form.asset.default = model.asset_id or 0
        file_assign_form.process(request.form)

        if request.method == "POST" and file_assign_form.validate():
            try:
                model.assign(file_assign_form.asset.data)
            except ValueError as e:
                flash(f"Failed to assign file to asset: {e}", 'error')
                return redirect(url_for("file.details_view", id=id))
            
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
    @require_write_access
    def upload_view(self):
        dropzone_path = get_dropzone_path()
        dropzone_files = get_dropzone_files()

        id = get_mdict_item_or_list(request.args, 'id')
        if id:
            assign_asset = db.session.query(Asset).get(id)
        else:
            assign_asset = None

        batch_number = get_next_file_batch_number()

        form = FileForm(request.form, batch_number=batch_number)
        dropzone_form = DropzoneFileForm(request.form, batch_number=batch_number)
        if request.method == 'POST' and not form.validate():
            if request.form.get('xhr', False):
                return jsonify(error=True, form_errors=form.errors), 400
        if request.method == 'POST' and form.validate():
            files: list[File] = []
            image_files: list[File] = []
            num_files = len(request.files.getlist("files"))
            print(f"Saving {num_files} files...")

            file_list: list[FileStorage] = request.files.getlist("files")
            file_list.sort(key=lambda f: f.filename)

            duplicate_files: list[tuple[str | None, File]] = []

            for file in file_list:

                try:
                    file_db  = upload_file(file, form.category.data, form.batch_number.data, form.privacy.data)
                except DuplicateFile as e:
                    duplicate_files.append((file.filename, e.matching_file))
                    continue

                if file_db.is_image:
                    image_files.append(file_db)
                
                files.append(file_db)

            #if current_app.config["MULTIPROCESSING_ENABLED"]:
            #    pool = mp.Pool(mp.cpu_count(), maxtasksperchild=1)
            #else:
            #    pool = None
            
            # Temporarily disable multiprocessing due to an issue with references in SQLAlchemy models
            pool = None

            if assign_asset:
                for file in files:
                    file.assign(assign_asset.id)
            else:
                print("Reading barcodes...")
                # Read barcodes in parallel
                if form.auto_assign.data and image_files:
                    if pool is not None:
                        result_objects = [pool.apply_async(File.read_rh_barcode, args=(file,)) for file in image_files]
                        asset_ids = [r.get() for r in result_objects]
                    else:
                        asset_ids = [File.read_rh_barcode(file) for file in image_files]
                    for file, asset_id in zip(image_files, asset_ids):
                        if not asset_id:
                            continue
                        try:
                            file.assign(asset_id)
                        except ValueError:
                            # Probably failed to assign file to asset because asset doesn't exist
                            # Ignore this
                            pass

            print("Creating thumbnails...")
            # Create thumbnails in parallel
            if image_files:
                if pool is not None:
                    result_objects = [pool.apply_async(File.make_thumbnail, args=(file,)) for file in image_files]
                    for file, result in zip(image_files, [r.get() for r in result_objects]):
                        if result:
                            file.has_thumbnail = True
                else:
                    result_objects = [File.make_thumbnail(file) for file in image_files]

            if pool is not None:
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
                return redirect(location=assign_asset.url)
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
        return self.render('admin/file/upload.html', form=form, dropzone_path=dropzone_path, dropzone_files=dropzone_files, dropzone_form=dropzone_form)
    
    @expose('/process-dropzone/', methods=['POST', 'GET'])
    @require_write_access
    def process_dropzone_view(self):
        dropzone_files = get_dropzone_files()

        batch_number = get_next_file_batch_number()

        dropzone_form = DropzoneFileForm(request.form, batch_number=batch_number)

        if request.method == 'POST' and dropzone_form.validate():
            duplicate_files: list[tuple[str | None, File]] = []
            for filepath in dropzone_files:
                try:
                    file: File = upload_file(file=filepath, batch_number=batch_number, privacy=dropzone_form.privacy.data)
                except DuplicateFile as e:
                    duplicate_files.append((filepath.name, e.matching_file))
                    continue

                asset_id = parse_hh_code(filepath.name.split('.')[0].split('_')[0])
                if asset_id and dropzone_form.auto_assign.data:
                    try:
                        file.assign(asset_id)
                    except ValueError:
                        # Probably failed to assign file to asset because asset doesn't exist
                        # Ignore this
                        pass

                db.session.add(file)
            db.session.commit()
            flash(f"{len(dropzone_files)} files processed", 'success')

            return redirect(url_for("file.upload_result_view", batch_number=batch_number, 
                                duplicate_files=repr([(f0, f1.id) for f0, f1 in duplicate_files]),))
        
        return redirect(url_for("file.upload_view"))

    @expose('/upload/result', methods=['GET'])
    @require_write_access
    def upload_result_view(self):
        order_by_str = request.args.get('order_by', 'upload_date')
        if order_by_str == "upload_date":
            order_by = File.upload_date
        elif order_by_str == "filename":
            order_by = File.filepath
        else:
            abort(403)
        
        if 'batch_number' in request.args:
            batch_number = request.args['batch_number']
            assert 'files' not in request.args

            files = db.session.query(File).filter(File.batch_number == batch_number) \
                .order_by(order_by).all()
        else:
            batch_number = None
            files: list[File] = []
            file_id_list: list[int] = simple_eval.eval(request.args['files'])
            for file_id in file_id_list:
                assert isinstance(file_id, int)
                files.append(db.session.query(File).get(file_id))
        
        duplicate_files = []
        if 'duplicate_files' in request.args:
            for f0, f1_id in simple_eval.eval(request.args['duplicate_files']):
                duplicate_files.append((f0, db.session.query(File).get(f1_id)))
        
        if 'auto_assign' in request.args:
            auto_assign = simple_eval.eval(request.args['auto_assign'])
        else:
            auto_assign = None

        if 'duplicate_count' in request.args:
            duplicate_count = simple_eval.eval(request.args['duplicate_count'])
        else:
            duplicate_count = None
        
        return self.render('admin/file/upload_result.html', files=files, duplicate_files=duplicate_files, auto_assign=auto_assign, batch_number=batch_number, duplicate_count=duplicate_count, order_by=order_by_str)


    @expose('/make_thumbnail/', methods=['POST'])
    @require_write_access
    def make_thumbnail_view(self):
        id = get_mdict_item_or_list(request.args, 'id')
        model = self.get_one(id)
        assert isinstance(model, File)

        if model.make_thumbnail():
            db.session.add(model)
            log("Update", model, user=current_user)
            db.session.commit()
            flash("Thumbnail created", 'success')
        else:
            flash("Thumbnail creation failed", 'danger')
        return redirect(url_for("file.details_view", id=id))
    
    @expose('/rotate/', methods=['POST'])
    @require_write_access
    def rotate_view(self):
        htmx = request.args.get('htmx', False)
        id = get_mdict_item_or_list(request.args, 'id')
        model = self.get_one(id)
        assert isinstance(model, File)

        if model.filename.lower().split('.')[-1] not in ('jpg', 'jpeg'):
            flash("Sorry, rotation is currently only available for JPEG files.", 'error')
            if htmx:
                return 'NG', 200, {'HX-Refresh': 'true'}
        else:
            rotation = int(get_mdict_item_or_list(request.args, 'rotation'))
            if rotation not in (90, 180, 270):
                flash("Invalid rotation value.", 'error')
                return redirect(url_for("file.details_view", id=id))

            model.rotate(rotation)
            db.session.add(model)
            log("Update", model, user=current_user, action="rotate", rotation=rotation)
            db.session.commit()
        
            if htmx:
                rnd = ''.join(random.choice(string.ascii_lowercase) for i in range(10))
                return get_template_attribute('_macros.html', 'render_file_thumbnail')(model, rnd)

            flash("Image rotated", 'success')

        return redirect(url_for("file.details_view", id=id))
    
    @expose('/assign/', methods=['POST'])
    @require_write_access
    def assign_view(self):
        id = get_mdict_item_or_list(request.args, 'id')
        model: File | None = self.get_one(id)
        if not model:
            flash('Record does not exist.', 'error')
            return redirect(url_for("file.details_view", id=id))
        assert isinstance(model, File)

        if 'asset_id' in request.form:
            asset_id = int(request.form['asset_id'])
        else:
            asset_id = int(request.args['asset_id'])

        try:
            model.assign(asset_id)
        except ValueError as e:
            flash(f"Failed to assign file to asset: {e}", 'error')
            return redirect(url_for("file.details_view", id=id))
        
        db.session.add(model)
        log("Update", model, user=current_user)
        db.session.commit()

        flash(f"File assigned to asset #{asset_id}", 'success')
        if request.args.get('refresh', False):
            return 'OK', 200, {'HX-Refresh': 'true'}
        
        return redirect(url_for('.details_view', id=id))
    
    @expose('/set_primary/', methods=['POST'])
    @require_write_access
    def set_primary_view(self):
        id = get_mdict_item_or_list(request.args, 'id')
        model = self.get_one(id)
        assert isinstance(model, File)

        model.primary = request.args.get('primary') == "True"
        db.session.add(model)
        db.session.commit()
        
        if request.args.get('refresh', False):
            return 'OK', 200, {'HX-Refresh': 'true'}
        
        return redirect(url_for('.details_view', id=id))
    
    @expose('/auto_assign/', methods=['POST'])
    @require_write_access
    def auto_assign_view(self):
        id = get_mdict_item_or_list(request.args, 'id')
        model = self.get_one(id)
        assert isinstance(model, File)

        asset_id = model.auto_assign()
        if asset_id:
            db.session.add(model)
            log("Update", model, user=current_user)
            db.session.commit()
            flash(f"Automatically assigned to asset #{asset_id:05}", 'success')
        else:
            flash("No RH barcode found.", 'success')
        return redirect(url_for("file.details_view", id=id))

    @expose('/delete/', methods=['POST'])
    @require_write_access
    def delete_view(self):
        htmx = request.args.get('htmx', False)
        id = get_mdict_item_or_list(request.args, 'id')
        model = self.get_one(id)
        assert isinstance(model, File)

        model.delete()
        db.session.add(model)
        db.session.commit()

        if htmx:
            return 'OK', 200, {'HX-Refresh': 'true'}

        flash("File deleted.", 'success')

        return redirect(url_for("file.details_view", id=id))