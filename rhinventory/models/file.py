import datetime
import os
import enum
import subprocess
from typing import TYPE_CHECKING, Literal

from PIL.ImageFile import ImageFile
from flask import current_app, url_for
from sqlalchemy import BigInteger, Integer, String, Text, \
    DateTime, LargeBinary, ForeignKey, Enum, Boolean
from sqlalchemy.orm import Relationship, relationship, Mapped, mapped_column
from PIL import Image, ImageEnhance, ImageOps

from rhinventory.models.enums import Privacy
from rhinventory.models.user import User
if TYPE_CHECKING:
    from rhinventory.db import Asset, Transaction
try:
    from pyzbar import pyzbar
except Exception as ex:
    print("Warning: Failed to import zbar:", ex)
    pyzbar = None

from rhinventory.extensions import db


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
    screenshot  = 16

    dump        = 20
    dump_metadata = 21

    text        = 30
    prose       = 31
    transcription = 32
    document    = 33

    test_result = 40

    raw_scan    = 50

    collection  = 90

IMAGE_CATEGORIES = [FileCategory.image, FileCategory.photo, FileCategory.scan,
                    FileCategory.cover_page, FileCategory.index_page, FileCategory.logo,
                    FileCategory.screenshot]

def get_next_file_batch_number() -> int:
    largest_batch_file = db.session.query(File).filter(File.batch_number != None) \
        .order_by(File.batch_number.desc()).limit(1).scalar()
        
    if largest_batch_file is None or largest_batch_file.batch_number is None:
        return 1
    else:
        return largest_batch_file.batch_number + 1

class File(db.Model):
    __tablename__ = 'files'
    id: Mapped[int] = mapped_column(primary_key=True)
    filepath: Mapped[str] = mapped_column(String, nullable=False)
    storage: Mapped[FileStore] = mapped_column(Enum(FileStore), nullable=False)
    primary: Mapped[bool] = mapped_column(nullable=False, default=False)
    has_thumbnail: Mapped[bool] = mapped_column(nullable=False, default=False) # _thumb
    category: Mapped[FileCategory | None] = mapped_column(Enum(FileCategory))
    title: Mapped[str | None] = mapped_column(String)
    comment: Mapped[str | None] = mapped_column(Text)
    analyzed: Mapped[datetime.datetime | None] = mapped_column() # last time it was scanned digitally for barcodes for example
    upload_date: Mapped[datetime.datetime | None] = mapped_column()
    batch_number: Mapped[int | None] = mapped_column(default=0)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    asset_id: Mapped[int | None] = mapped_column(ForeignKey('assets.id'))
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey('transactions.id'))
    benchmark_id: Mapped[int | None] = mapped_column(ForeignKey('benchmark.id'))
    md5: Mapped[bytes | None] = mapped_column(LargeBinary(16))
    original_md5: Mapped[bytes | None] = mapped_column(LargeBinary(16))
    sha256: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    original_sha256: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    blake3: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    is_deleted: Mapped[bool | None] = mapped_column(default=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=True)

    privacy: Mapped[Privacy] = mapped_column(Enum(Privacy), default=Privacy.private_implicit, nullable=False)

    user: Relationship[User | None] = relationship(User, backref="files")
    asset: Relationship["Asset | None"] = relationship("Asset", backref="files")
    transaction: Relationship["Transaction | None"] = relationship("Transaction", backref="files")
    #transaction = relationship("Benchmark", backref="files")

    # TODO constraint on only one asset/transaction/benchmark relationship
    #CheckConstraint()

    THUMBNAIL_SIZE = (800, 800)

    def __repr__(self) -> str:
        return f'<File {self.id} {self.filepath}>'
    
    @property
    def is_image(self) -> bool:
        return self.category in IMAGE_CATEGORIES
    
    @property
    def filepath_thumbnail(self) -> str:
        path = self.filepath.split('.')
        path[-2] += '_thumb'
        return '.'.join(path) 
    
    def thumbnail_file_exists(self) -> bool:
        return os.path.exists(self.full_filepath_thumbnail)
    
    @property
    def filename(self) -> str:
        return self.filepath.split('/')[-1]
    
    @property
    def file_extension(self) -> str:
        return self.filepath.split('.')[-1]
    
    @property
    def _file_store_path(self) -> str:
        return current_app.config['FILE_STORE_LOCATIONS'][self.storage.value]

    @property
    def full_filepath(self) -> str:
        return os.path.join(self._file_store_path, self.filepath)
    
    @property
    def full_filepath_thumbnail(self) -> str:
        return os.path.join(self._file_store_path, self.filepath_thumbnail)

    @property
    def url(self) -> str:
        return url_for('file', file_id=self.id, filename=self.filename)
    
    @property
    def url_thumbnail(self) -> str:
        return url_for('file', file_id=self.id, filename=self.filename, thumb=True)
    
    def open_image(self) -> None | ImageFile:
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
        if self.filename.endswith('.pdf'):
            # PDF files are not supported for thumbnail generation
            return False
        im = self.open_image()
        if not im:
            return False
        im = ImageOps.exif_transpose(im)
        im.thumbnail(self.THUMBNAIL_SIZE)
        im.save(os.path.join(self.full_filepath_thumbnail))
        self.has_thumbnail = True
        return True
    
    def rotate(self, rotation: Literal[0] | Literal[90] | Literal[180] | Literal[270] | None = None, make_thumbnail: bool=True):
        if not self.is_image:
            return
        
        if self.filename.lower().split('.')[-1] not in ('jpg', 'jpeg'):
            return
        
        command: list[str]
        if rotation == 0:
            command = ["exiftran", '-a', '-ni', '-i', self.full_filepath]
        else:
            option: list[str] = {
                0: ['-a', '-no'],
                90: ['-9'],
                180: ['-1'],
                270: ['-2'],
                None: ['-a'],
            }[rotation]

            command = ["exiftran", *option, '-i', self.full_filepath]
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
        if not pyzbar:
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
    
    def assign(self, asset_id: int):
        '''Assigns File to a given Asset and renames file and thumbnail'''

        from rhinventory.models.asset import Asset # avoid circular import

        if not asset_id:
            return
        
        # check that asset exists
        asset = Asset.query.get(asset_id)
        if not asset:
            raise ValueError("Trying to assign to asset that does not exist")

        self.asset_id = asset_id

        files_dir = current_app.config['FILE_STORE_LOCATIONS'][self.storage.value]
        assert isinstance(files_dir, str)

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
        else:
            old_filepath_thumbnail = None
        
        self.filepath = new_filepath

        if old_filepath_thumbnail:
            os.rename(os.path.join(files_dir, old_filepath_thumbnail), os.path.join(files_dir, self.filepath_thumbnail))

    def calculate_md5sum(self):
        # Let's launch a subprocess to (hopefully) be faster
        result = subprocess.run(["md5sum", self.full_filepath], capture_output=True)
        if result.returncode == 0:
            hash = bytes.fromhex(result.stdout.split()[0].decode('ascii'))
            self.md5 = hash
        