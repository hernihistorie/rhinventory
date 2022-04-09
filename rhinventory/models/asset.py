import enum
from attr import attributes

from sqlalchemy import Column, Integer, Numeric, String, Text, \
    DateTime, LargeBinary, ForeignKey, Enum, Table, Index, Boolean, CheckConstraint
from sqlalchemy.orm import relationship, backref

from rhinventory.models.file import File, IMAGE_CATEGORIES
from rhinventory.extensions import db

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

    #num_photos  = Column(Integer)

    condition   = Column(Integer, default=0, nullable=False)
    functionality = Column(Integer, default=0, nullable=False)
    status      = Column(Enum(AssetStatus), default=AssetStatus.unknown, nullable=False)

    location_id = Column(Integer, ForeignKey('locations.id'))
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    medium_id   = Column(Integer, ForeignKey('media.id'))
    hardware_type_id  = Column(Integer, ForeignKey('hardware_type.id'))

    children    = relationship("Asset",
                    backref=backref("parent", remote_side=id),
        )
    location    = relationship("Location", backref="assets")
    category    = relationship("Category", backref="assets")
    medium      = relationship("Medium", backref="assets")
    hardware_type = relationship("HardwareType", backref="assets")

    transactions = relationship(
        "Transaction",
        secondary='transaction_assets')

    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=True)
    organization = relationship("Organization")

    def __str__(self):
        return f"{self.code} {self.name}"
    
    @property
    def code(self):
        string = ""
        if self.organization:
            string += f"{self.organization.shortname}: "

        if self.category.expose_number:
            string += f"{self.category.prefix}{self.custom_code}"
        else:
            if self.id is not None:
                string += f"{self.id:05}"
            else:
                string += "XXXXX"
        
        return string



    def get_primary_image(self):
        return db.session.query(File).filter(File.asset_id==self.id and File.category in IMAGE_CATEGORIES).order_by(File.primary.desc(), File.has_thumbnail.desc(), File.filepath.asc()).first()


class Category(db.Model):
    __tablename__ = 'categories'
    id          = Column(Integer, primary_key=True)
    name        = Column(String, nullable=False)
    prefix      = Column(String)
    counter     = Column(Integer)
    color       = Column(String)
    expose_number = Column(Boolean, nullable=False, default=True)

    def __str__(self):
        return f"{self.name}"


class CategoryTemplate(db.Model):
    __tablename__ = 'category_templates'
    id          = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey('categories.id'))
    key         = Column(String, nullable=False)
    value       = Column(String)

    category    = relationship("Category", backref="templates")


class AssetMeta(db.Model):
    __tablename__ = 'assets_meta'
    id          = Column(Integer, primary_key=True)
    asset_id    = Column(Integer, ForeignKey('assets.id'))
    key         = Column(String, nullable=False)
    value       = Column(Text)

    asset       = relationship("Asset", backref="metadata")


class Medium(db.Model):
    __tablename__ = 'media'
    id          = Column(Integer, primary_key=True)
    name        = Column(String, nullable=False)
        
    def __str__(self):
        return f"{self.name}"
