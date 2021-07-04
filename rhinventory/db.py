import enum
import json
import datetime
import os
import os.path

from flask import current_app
from sqlalchemy import Column, Integer, Numeric, String, Text, \
    DateTime, LargeBinary, ForeignKey, Enum, Table, Index, Boolean
from sqlalchemy.orm import relationship, backref
from dictalchemy import make_class_dictable
from sqlalchemy.sql.expression import text
from PIL import Image, ImageEnhance
from pyzbar import pyzbar

from rhinventory.extensions import db

make_class_dictable(db.Model)

class User(db.Model):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(255))
    read_access = Column(Boolean(), nullable=False, default=False)
    write_access = Column(Boolean(), nullable=False, default=False)
    admin = Column(Boolean(), nullable=False, default=False)

    github_access_token = Column(String(255))
    github_id = Column(Integer)
    github_login = Column(String(255))

    #person_id = Column(Integer, ForeignKey('people.id'))
    #person = relationship("Person")

    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_active(self):
        return True
    
    @property
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.id)
    
    def __str__(self):
        return self.username or self.github_login


class Person(db.Model):
    __tablename__ = 'people'
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    email = Column(String(255))
    note = Column(Text)

class AssetStatus(enum.Enum):
    unknown = 0
    owned = 1
    lent = 2

    lost = -1
    discarded = -2


class Asset(db.Model):
    __tablename__ = 'assets'
    id          = Column(Integer, primary_key=True)
    parent_id   = Column(Integer, ForeignKey('assets.id'))
    name        = Column(String, nullable=False)
    manufacturer = Column(String)
    model       = Column(String)
    custom_code = Column(Integer)
    note        = Column(Text)
    serial      = Column(String)

    num_photos  = Column(Integer)

    condition   = Column(Integer, nullable=False)
    functionality = Column(Integer, nullable=False)
    status      = Column(Enum(AssetStatus), nullable=False)

    location_id = Column(Integer, ForeignKey('locations.id'))
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    medium_id   = Column(Integer, ForeignKey('media.id'))

    children    = relationship("Asset",
                    backref=backref("parent", remote_side=id),
        )
    location    = relationship("Location", backref="assets")
    category    = relationship("Category", backref="assets")
    medium      = relationship("Medium", backref="assets")

    transactions = relationship(
        "Transaction",
        secondary='transaction_assets')

    def __str__(self):
        if self.id is not None:
            return f"RH{self.id:05} {self.name}"
        else:
            return f"RHXXXXX {self.name}"

    def get_primary_image(self):
        return db.session.query(File).filter(File.asset_id==self.id and File.category in IMAGE_CATEGORIES).order_by(File.primary.desc(), File.has_thumbnail.desc()).first()


class Category(db.Model):
    __tablename__ = 'categories'
    id          = Column(Integer, primary_key=True)
    name        = Column(String, nullable=False)
    prefix      = Column(String)
    counter     = Column(Integer)
    color       = Column(String)

    def __str__(self):
        return f"{self.name}"


class CategoryTemplate(db.Model):
    __tablename__ = 'category_templates'
    id          = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey('categories.id'))
    key         = Column(String, nullable=False)
    value       = Column(String)

    category    = relationship("Category", backref="templates")


class TransactionType(enum.Enum):
    unknown     = 0

    acquisition = 1
    disposal    = -1

    purchase    = 2
    sale        = -2

    donation_in = 3
    donation_out = -3

    creation    = 4
    loss        = -4

    borrow      = 5
    return_out  = -5

    return_in   = 6
    lend        = -6

# TODO this class should use the person database, not user and string
class Transaction(db.Model):
    __tablename__ = 'transactions'
    id          = Column(Integer, primary_key=True)
    transaction_type = Column(Enum(TransactionType))
    user_id     = Column(Integer) # TODO ForeignKey
    counterparty = Column(String)
    cost        = Column(Numeric)
    note        = Column(Text)
    date        = Column(DateTime)

    assets      = relationship(
        "Asset",
        secondary='transaction_assets')


transaction_assets = Table('transaction_assets', db.Model.metadata,
    Column('transaction_id', Integer, ForeignKey('transactions.id')),
    Column('asset_id', Integer, ForeignKey('assets.id'))
)


class Location(db.Model):
    __tablename__ = 'locations'
    id          = Column(Integer, primary_key=True)
    parent_id   = Column(Integer, ForeignKey('locations.id'))
    name        = Column(String, nullable=False)
    note        = Column(Text)
    
    children    = relationship("Location",
                    backref=backref("parent", remote_side=id),
        )
    def __str__(self):
        return f"{self.name}"


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
    user_id     = Column(Integer, ForeignKey('users.id'))
    asset_id    = Column(Integer, ForeignKey('assets.id'))

    user        = relationship("User", backref="files")
    asset       = relationship("Asset", backref="files")

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
    
    @property
    def filename(self):
        return self.filepath.split('/')[-1]
    
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
        im.thumbnail(self.THUMBNAIL_SIZE)
        im.save(os.path.join(files_dir, self.filepath_thumbnail))
        self.has_thumbnail = True
    
    def read_barcodes(self, symbols=None):
        if not self.is_image:
            return
        im = self.open_image()
        im = ImageEnhance.Color(im).enhance(0)
        im = ImageEnhance.Contrast(im).enhance(2)
        im = ImageEnhance.Sharpness(im).enhance(-1)
        im.thumbnail((1200, 1200))
        if symbols:
            return pyzbar.decode(im, symbols=symbols)
        else:
            return pyzbar.decode(im)
    
    def read_rh_barcode(self):
        if not self.is_image:
            return
        barcodes = self.read_barcodes(symbols=[pyzbar.ZBarSymbol.CODE128])
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






class AssetMeta(db.Model):
    __tablename__ = 'assets_meta'
    id          = Column(Integer, primary_key=True)
    asset_id    = Column(Integer, ForeignKey('assets.id'))
    key         = Column(String, nullable=False)
    value       = Column(Text)

    asset       = relationship("Asset", backref="metadata")


class EventStatus(enum.Enum):
    unknown     = 0

    expected    = 1
    confirmed   = 2
    
    in_progress = 10

    finished    = 20
    paid        = 21


class Event(db.Model):
    __tablename__ = 'events'
    id          = Column(Integer, primary_key=True)
    name        = Column(String, nullable=False)
    place       = Column(String)
    date_from   = Column(DateTime)
    date_to     = Column(DateTime)
    status      = Column(Enum(EventStatus))

    checks      = relationship(
        "Check",
        secondary=lambda: event_checks,
        backref="events")
        
    def __str__(self):
        return f"{self.name}"



class CheckType(enum.Enum):
    unknown     = 0

    full        = 1
    partial     = 2
    before_event = 3
    after_event  = 4

class CheckStatus(enum.Enum):
    unknown     = 0

    started     = 1
    ended       = 2
    validated   = 3


class Check(db.Model):
    __tablename__ = 'checks'
    id          = Column(Integer, primary_key=True)
    type        = Column(Enum(CheckType), nullable=False)
    user_id     = Column(Integer, ForeignKey('users.id'))
    date_from   = Column(DateTime)
    date_to     = Column(DateTime)
    status      = Column(Enum(CheckStatus))
    note        = Column(Text)

    user        = relationship(User)

    def __str__(self):
        return f"Inventura z {self.date_from}"

    


event_checks = Table('event_checks', db.Model.metadata,
    Column('event_id', Integer, ForeignKey('events.id')),
    Column('check_id', Integer, ForeignKey('checks.id'))
)


class CheckItem(db.Model):
    __tablename__ = 'check_items'
    id          = Column(Integer, primary_key=True)
    check_id    = Column(Integer, ForeignKey('checks.id'))
    barcode     = Column(String)
    original_barcode = Column(String)

    check       = relationship("Check", backref="items")


class CheckLogChange(enum.Enum):
    unknown     = 0

    ok          = 1
    not_found   = 2
    surplus     = 3
    wrong_location = 4


class CheckLog(db.Model):
    __tablename__ = 'check_logs'
    id          = Column(Integer, primary_key=True)
    check_id    = Column(Integer, ForeignKey('checks.id'))
    asset_id    = Column(Integer, ForeignKey('assets.id'))
    location_id = Column(Integer, ForeignKey('locations.id'))
    original_location_id = Column(Integer, ForeignKey('locations.id'))
    change      = Column(Enum(CheckLogChange))

    check       = relationship("Check", backref="logs")
    asset       = relationship("Asset", backref="logs")
    location    = relationship("Location", backref="check_logs", foreign_keys=[location_id])
    original_location = relationship("Location", foreign_keys=[original_location_id])


class Medium(db.Model):
    __tablename__ = 'media'
    id          = Column(Integer, primary_key=True)
    name        = Column(String, nullable=False)
        
    def __str__(self):
        return f"{self.name}"

# Old PC models follow


class Benchmark(db.Model):
    id          = Column(Integer, primary_key=True)
    name        = Column(String(255))
    benchmark_run_id  = Column(Integer, ForeignKey('benchmark_runs.id'))
    benchmark_type_id = Column(Integer, ForeignKey('benchmark_type.id'))
    computer_id = Column(Integer, ForeignKey('computer.id'))
    rundate     = Column(Integer)  # TODO: transform to DateTime
    runby       = Column(Integer)
    runok       = Column(Integer)
    simpleresult = Column(Numeric)
    results     = relationship('BenchmarkResult', backref='benchmark', lazy='dynamic')


class BenchmarkResult(db.Model):
    id          = Column(Integer, primary_key=True)
    benchmark_id = Column(Integer, ForeignKey('benchmark.id'))
    mime        = Column(String(255))
    content     = Column(LargeBinary)
    description = Column(String(4096))
    note        = Column(String(4096))


class BenchmarkRun(db.Model):
    __tablename__ = 'benchmark_runs'
    id          = Column(Integer, primary_key=True)
    name        = Column(String(255))
    rundate     = Column(DateTime)
    runby       = Column(Integer)  # TODO: link to user
    benchmarks  = relationship('Benchmark', backref='runs', lazy='dynamic')


class BenchmarkType(db.Model):
    id          = Column(Integer, primary_key=True)
    name        = Column(String(255))
    description = Column(String(4096))
    inputhelp   = Column(String(4096))
    resulthelp  = Column(String(4096))
    benchmarks  = relationship('Benchmark', backref='bench_type', lazy='dynamic')


class Computer(db.Model):
    id          = Column(Integer, primary_key=True)
    name        = Column(String(255))
    manufacturer = Column(String(255))
    model       = Column(String(255))
    nickname    = Column(String(255))
    description = Column(String(255))
    serial      = Column(String(255))
    image       = Column(String(255))
    status      = Column(Integer, ForeignKey('status.id'))
    condition   = Column(String(255))
    acq_from    = Column(String(255))
    acq_by      = Column(String(255))
    acq_for     = Column(String(255))
    note        = Column(String())
    hardware    = relationship('Hardware', backref='computer', lazy='dynamic')
    benchmarks  = relationship('Benchmark', backref='computer', lazy='dynamic')
    def __str__(self):
        return "PC{0} {1}".format(str(self.id).zfill(3), self.nickname)

class Hardware(db.Model):
    id              = Column(Integer, primary_key=True)
    hardware_type   = Column(Integer, ForeignKey('hardware_type.id'))
    computer_id     = Column(Integer, ForeignKey('computer.id'))
    name            = Column(String(255))
    manufacturer    = Column(String(255))
    model           = Column(String(255))
    serial          = Column(String(255))
    description     = Column(String(255))
    image           = Column(String(255))
    status          = Column(Integer, ForeignKey('status.id'))
    condition       = Column(String(255))
    acq_from        = Column(String(255))
    acq_by          = Column(String(255))
    acq_for         = Column(String(255))
    note            = Column(String())

    def __str__(self):
        return "PK{0} {1}".format(str(self.id).zfill(4), self.name)


class HardwareType(db.Model):
    __tablename__ = 'hardware_type'
    id          = Column(Integer, primary_key=True)
    name        = Column(String(255))
    description = Column(String(255))
    icon        = Column(String(255))
    items       = relationship('Hardware', backref='type', lazy='dynamic')

    def __str__(self):
        return self.name


class Status(db.Model):
    id      = Column(Integer, primary_key=True)
    name    = Column(String(255))

#tables = [AssetMeta,
#    Category, CategoryTemplate, Medium, Location # Transaction removed
#    #Event, Check, CheckItem, CheckLog, 
#    #Benchmark, BenchmarkType, Computer, Hardware,
#]

LogEvent = enum.Enum('LogEvent', ["Create", "Update", "Delete", "Other"])

class LogItem(db.Model):
    __tablename__ = 'logs'
    id          = Column(Integer, primary_key=True)
    
    table       = Column(String(80), nullable=False)
    object_id   = Column(Integer, nullable=False)
    event       = Column(Enum(LogEvent), nullable=False)
    object_json = Column(Text)
    
    extra_json  = Column(Text)
    
    user_id     = Column(Integer, ForeignKey('users.id'))
    user        = relationship(User)
    
    datetime    = Column(DateTime, nullable=False)
    
    idx_obj     = Index('table', 'object_id', unique=True)
    
    @property
    def object(self):
        # don't judge me
        class_ = globals()[self.object_class]
        assert issubclass(class_, db.Model)
        return class_.query.get(self.object_id)


def log(event, object, log_object=True, user=None, **kwargs):
    log_item = LogItem(table=type(object).__name__, object_id=object.id,
        event=event, object_json=json.dumps(object.asdict(), default=repr) if log_object else None,
        user_id=user.id if user else None,
        datetime=datetime.datetime.now(),
        extra_json=json.dumps(kwargs))
    db.session.add(log_item)


