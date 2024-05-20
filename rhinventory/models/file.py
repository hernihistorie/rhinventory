import os
import enum
import subprocess

from flask import current_app, url_for
from sqlalchemy import Column, Integer, Numeric, String, Text, \
    DateTime, LargeBinary, ForeignKey, Enum, Table, Index, Boolean, CheckConstraint
from sqlalchemy.orm import relationship, backref, Mapped, mapped_column
from PIL import Image, ImageEnhance, ImageOps

from rhinventory.models.enums import Privacy
try:
    from pyzbar import pyzbar
except Exception as ex:
    print("Warning: Failed to import zbar:", ex)
    pyzbar = None

from rhinventory.extensions import db
from rhinventory.models.computers import Benchmark


class FileStore(enum.Enum):
    local = "local"
    local_nas = "local_nas"

class FileCategory(enum.Enum):
    unknown     = 0
    other       = 1

    image       = 10
    photo       = 11
    scan        = 12
    cover_page  = 13
    index_page  = 14
    logo        = 15

    dump        = 20
    dump_metadata = 21

    text        = 30
    prose       = 31
    transcription = 32

    test_result = 40

    raw_scan    = 50

    collection  = 90

IMAGE_CATEGORIES = [FileCategory.image, FileCategory.photo, FileCategory.scan,
                    FileCategory.cover_page, FileCategory.index_page, FileCategory.logo]

def get_next_file_batch_number():
    largest_batch_file = db.session.query(File).filter(File.batch_number != None) \
        .order_by(File.batch_number.desc()).limit(1).scalar()
        
    if largest_batch_file is None or largest_batch_file.batch_number is None:
        return 1
    else:
        return largest_batch_file.batch_number + 1

class File(db.Model):
    __tablename__ = 'files'
    id          = Column(Integer, primary_key=True)
    filepath    = Column(String, nullable=False)
    storage     = Column(Enum(FileStore), nullable=False)
    primary     = Column(Boolean, nullable=False, default=False)
    has_thumbnail = Column(Boolean, nullable=False, default=False) # _thumb
    category    = Column(Enum(FileCategory))
    title       = Column(String)
    comment     = Column(Text)
    analyzed    = Column(DateTime) # last time it was scanned digitally for barcodes for example
    upload_date = Column(DateTime)
    batch_number = Column(Integer, default=0)
    user_id     = Column(Integer, ForeignKey('users.id'))
    asset_id    = Column(Integer, ForeignKey('assets.id'))
    transaction_id = Column(Integer, ForeignKey('transactions.id'))
    benchmark_id   = Column(Integer, ForeignKey('benchmark.id'))
    md5         = Column(LargeBinary(16))
    original_md5 = Column(LargeBinary(16))
    sha256      = Column(LargeBinary(32))
    original_sha256 = Column(LargeBinary(32))
    is_deleted = Column(Boolean, default=False)
    size: Mapped[int] = mapped_column(Integer, nullable=True)

    privacy: Mapped[Privacy] = mapped_column(Enum(Privacy), default=Privacy.private_implicit, nullable=False)

    user        = relationship("User", backref="files")
    asset       = relationship("Asset", backref="files")
    transaction = relationship("Transaction", backref="files")
    #transaction = relationship("Benchmark", backref="files")

    # TODO constraint on only one asset/transaction/benchmark relationship
    #CheckConstraint()

    THUMBNAIL_SIZE = (800, 800)

    def __str__(self):
        return f"<File {self.filepath}>"
    
    @property
    def is_image(self):
        return self.category in IMAGE_CATEGORIES
    
    @property
    def filepath_thumbnail(self):
        path = self.filepath.split('.')
        path[-2] += '_thumb'
        return '.'.join(path) 
    
    def thumbnail_file_exists(self):
        return os.path.exists(self.full_filepath_thumbnail)
    
    @property
    def filename(self):
        return self.filepath.split('/')[-1]
    
    @property
    def _file_store_path(self) -> str:
        return current_app.config['FILE_STORE_LOCATIONS'][self.storage.value]

    @property
    def full_filepath(self):
        return os.path.join(self._file_store_path, self.filepath)
    
    @property
    def full_filepath_thumbnail(self):
        return os.path.join(self._file_store_path, self.filepath_thumbnail)

    @property
    def url(self) -> str:
        return url_for('file', file_id=self.id, filename=self.filename)
    
    @property
    def url_thumbnail(self) -> str:
        return url_for('file', file_id=self.id, filename=self.filename, thumb=True)
    
    def open_image(self):
        if not self.is_image:
            return
        if self.filepath.endswith('.svg'):
            return
        im = Image.open(self.full_filepath)
        return im

    def delete(self) -> None:
        if os.path.exists(self.full_filepath):
            os.remove(self.full_filepath)
        if self.full_filepath_thumbnail and os.path.exists(self.full_filepath_thumbnail):
            os.remove(self.full_filepath_thumbnail)
        
        self.is_deleted = True
    
    # Make sure to save the model after calling this method...
    def make_thumbnail(self):
        if not self.is_image:
            return False
        im = self.open_image()
        if not im:
            return False
        im = ImageOps.exif_transpose(im)
        im.thumbnail(self.THUMBNAIL_SIZE)
        im.save(os.path.join(self.full_filepath_thumbnail))
        self.has_thumbnail = True
        return True
    
    def rotate(self, rotation=None, make_thumbnail=True):
        if not self.is_image:
            return
        
        if self.filename.lower().split('.')[-1] not in ('jpg', 'jpeg'):
            return
        
        if rotation == 0:
            command = ["exiftran", '-a', '-ni', '-i', self.full_filepath]
        else:
            option = {
                0: ['-a', '-no'],
                90: '-9',
                180: '-1',
                270: '-2',
                None: '-a',
            }[rotation]

            command = ["exiftran", option, '-i', self.full_filepath]
        result = subprocess.run(command, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError("exiftran failed: " + repr(result))
        
        if self.original_md5 is None:
            self.original_md5 = self.md5
        
        self.calculate_md5sum()

        if make_thumbnail:
            self.make_thumbnail()
    
    def read_barcodes(self, symbols=None):
        if pyzbar is None:
            print("Warning: pyzbar was not found, thus no barcode detection was done.")
            return None

        if not self.is_image:
            return
        im = self.open_image()
        if not im:
            return
        try:
            im = ImageEnhance.Color(im).enhance(0)
            im = ImageEnhance.Contrast(im).enhance(2)
            im = ImageEnhance.Sharpness(im).enhance(-1)
        except ValueError:
            return None
        
        im.thumbnail((1200, 1200))

        if symbols:
            return pyzbar.decode(im, symbols=symbols)
        else:
            return pyzbar.decode(im)
    
    def read_rh_barcode(self):
        if not self.is_image:
            return
        barcodes = self.read_barcodes(symbols=[pyzbar.ZBarSymbol.CODE128])
        if not barcodes:
            return
        for barcode in barcodes:
            if barcode.type == "CODE128" and barcode.data.decode('utf-8').startswith("RH") or barcode.data.decode('utf-8').startswith("HH"):
                try:
                    asset_id = int(barcode.data.decode('utf-8')[2:])
                except Exception:
                    continue
                return asset_id

    def auto_assign(self):
        if not self.is_image:
            return
        # only read CODE128 to speed up decoding
        asset_id = self.read_rh_barcode()
        if asset_id:
            self.assign(asset_id)
    
    def assign(self, asset_id):
        '''Assigns File to a given Asset and renames file and thumbnail'''
        if not asset_id:
            return
        self.asset_id = asset_id

        files_dir = current_app.config['FILE_STORE_LOCATIONS'][self.storage.value]

        directory = f'assets/{asset_id}'
        os.makedirs(files_dir + "/" + directory, exist_ok=True)
        new_filepath = f'{directory}/{self.filename}'

        while os.path.exists(os.path.join(files_dir, new_filepath)):
            p = new_filepath.split('.')
            p[-2] += '_1'
            new_filepath = '.'.join(p)
        os.rename(os.path.join(files_dir, self.filepath), os.path.join(files_dir, new_filepath))
        if self.has_thumbnail:
            old_filepath_thumbnail = self.filepath_thumbnail
        
        self.filepath = new_filepath

        if self.has_thumbnail:
            os.rename(os.path.join(files_dir, old_filepath_thumbnail), os.path.join(files_dir, self.filepath_thumbnail))

    def calculate_md5sum(self):
        # Let's launch a subprocess to (hopefully) be faster
        result = subprocess.run(["md5sum", self.full_filepath], capture_output=True)
        if result.returncode == 0:
            hash = bytes.fromhex(result.stdout.split()[0].decode('ascii'))
            self.md5 = hash
        