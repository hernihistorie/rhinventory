import enum

from flask import Flask
from flask_admin import Admin
from flask_sqlalchemy import SQLAlchemy
from flask_admin.contrib.sqla import ModelView
from sqlalchemy import Column, Integer, Numeric, String, Text, \
    DateTime, LargeBinary, ForeignKey, Enum, Table
from sqlalchemy.orm import relationship

# Create application
app = Flask(__name__)

# Create dummy secrey key so we can use sessions
app.config['SECRET_KEY'] = '123456790'

# Create in-memory database
app.config['DATABASE_FILE'] = 'rhinventory.db'
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + app.config['DATABASE_FILE']
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
#app.config['SQLALCHEMY_ECHO'] = True

db = SQLAlchemy(app)

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
    custom_code = Column(String)
    note        = Column(Text)
    serial      = Column(String)

    condition   = Column(Integer, nullable=False)
    functionality = Column(Integer, nullable=False)
    status      = Column(Enum(AssetStatus), nullable=False)

    location_id = Column(Integer, ForeignKey('locations.id'))
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)

    parent      = relationship("Asset")
    location    = relationship("Location", backref="assets")
    category    = relationship("Category", backref="assets")


class Category(db.Model):
    __tablename__ = 'categories'
    id          = Column(Integer, primary_key=True)
    name        = Column(String, nullable=False)
    prefix      = Column(String)
    counter     = Column(Integer)


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
        secondary=lambda: transaction_assets,
        backref="transactions")


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
    
    parent      = relationship("Location")



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
    user_id     = Column(Integer) # TODO
    date_from   = Column(DateTime)
    date_to     = Column(DateTime)
    status      = Column(Enum(CheckStatus))
    note        = Column(Text)


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

# Old PC models follow

class AuditLog(db.Model):
    id          = Column(Integer, primary_key=True)
    item_table  = Column(String)
    item_id     = Column(Integer)
    action      = Column(String)

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

db.create_all()

admin = Admin(app)

for table in (Asset, Benchmark, BenchmarkType, Computer, Hardware):
    admin.add_view(ModelView(table, db.session))

if __name__ == '__main__':
    app.run(debug=True)
