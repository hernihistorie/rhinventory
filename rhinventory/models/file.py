import os
import enum
import subprocess

from flask import current_app
from sqlalchemy import Column, Integer, Numeric, String, Text, \
    DateTime, LargeBinary, ForeignKey, Enum, Table, Index, Boolean, CheckConstraint
from sqlalchemy.orm import relationship, backref
from PIL import Image, ImageEnhance, ImageOps
try:
    from pyzbar import pyzbar
except Exception as ex:
    print("Warning: Failed to import zbar:", ex)
    pyzbar = None

from rhinventory.extensions import db
from rhinventory.models.computers import Benchmark


class FileCategory(enum.Enum):
    unknown     = 0
    other       = 1

    image       = 10
    photo       = 11
    scan        = 12

    dump        = 20
    dump_metadata = 21

    text        = 30
    prose       = 31
    transcription = 32

    collection  = 90

IMAGE_CATEGORIES = [FileCategory.image, FileCategory.photo, FileCategory.scan]

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
    storage     = Column(String, nullable=False)
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
        files_dir = current_app.config['FILES_DIR']
        return os.path.exists(os.path.join(files_dir, self.filepath_thumbnail))
    
    @property
    def filename(self):
        return self.filepath.split('/')[-1]
    
    @property
    def full_filepath(self):
        files_dir = current_app.config['FILES_DIR']
        return os.path.join(files_dir, self.filepath)
    
    def open_image(self):
        if not self.is_image:
            return
        files_dir = current_app.config['FILES_DIR']
        im = Image.open(os.path.join(files_dir, self.filepath))
        return im
    
    # Make sure to save the model after calling this method...
    def make_thumbnail(self):
        if not self.is_image:
            return
        files_dir = current_app.config['FILES_DIR']
        im = self.open_image()
        im = ImageOps.exif_transpose(im)
        im.thumbnail(self.THUMBNAIL_SIZE)
        im.save(os.path.join(files_dir, self.filepath_thumbnail))
        self.has_thumbnail = True
    
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
        if not self.is_image:
            return
        im = self.open_image()
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
            if barcode.type == "CODE128" and barcode.data.decode('utf-8').startswith("RH"):
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

        files_dir = current_app.config['FILES_DIR']

        directory = f'assets/{asset_id}'
        os.makedirs(current_app.config['FILES_DIR'] + "/" + directory, exist_ok=True)
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
        