import enum

from flask import current_app
from sqlalchemy import Column, Integer, Numeric, String, Text, \
    DateTime, LargeBinary, ForeignKey, Enum, Table, Index, Boolean, CheckConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql.expression import text

from rhinventory.extensions import db

from rhinventory.models.user import User
from rhinventory.models.asset import Asset, AssetStatus, Category, CategoryTemplate, AssetMeta, Medium
from rhinventory.models.transaction import TransactionType, Transaction
from rhinventory.models.file import FileCategory, File, IMAGE_CATEGORIES, get_next_file_batch_number
from rhinventory.models.log import log, LogEvent, LogItem


class Organization(db.Model):
    __tablename__ = 'organizations'
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    shortname = Column(String(16))
    url = Column(String(255))
    icon_url = Column(String(255))
    image_url = Column(String(255))
    visible = Column(Boolean)

    def __str__(self):
        return self.name


class Party(db.Model):
    __tablename__ = 'parties'
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    legal_name = Column(String(255))
    email = Column(String(255))
    is_person = Column(Boolean)
    note = Column(Text)

    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=True)
    organization = relationship("Organization", backref=backref("parties", order_by=id))

    def __str__(self):
        return self.name


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

# Old PC models follow


class Status(db.Model):
    id      = Column(Integer, primary_key=True)
    name    = Column(String(255))

#tables = [AssetMeta,
#    Category, CategoryTemplate, Medium, Location # Transaction removed
#    #Event, Check, CheckItem, CheckLog, 
#    #Benchmark, BenchmarkType, Computer, Hardware,
#]

