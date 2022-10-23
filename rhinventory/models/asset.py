import sys
import enum

from sqlalchemy import Column, Integer, Numeric, String, Text, \
    DateTime, LargeBinary, ForeignKey, Enum, Table, Index, Boolean, CheckConstraint, \
        ARRAY, desc
from sqlalchemy.orm import relationship, backref
from rhinventory.models.asset_attributes import Company, Platform, Medium, Packaging, ProductCode, AssetTag, asset_tag_table, asset_platform_table

from rhinventory.models.file import File, IMAGE_CATEGORIES, FileCategory
from rhinventory.extensions import db

TESTING = "pytest" in sys.modules

class AssetStatus(enum.Enum):
    unknown = 0
    owned = 1
    lent = 2

    lost = -1
    discarded = -2


class AssetCondition(enum.Enum):
    unknown = 0
    mint = 1
    scuffed = 2
    damaged = 3
    garbage = 4


class AssetCategory(enum.Enum):
    unknown = 0
    
    game = 1
    console = 2
    computer = 3
    console_accesory = 4
    computer_accessory = 5
    computer_component = 6
    computer_mouse = 7
    keyboard = 8
    television = 9
    monitor = 10
    software = 11
    multimedia = 12
    receipt = 13
    literature = 14
    other = 15
    rewritable_media = 16


class Asset(db.Model):
    __tablename__ = 'assets'
    CATEGORY_PREFIX = "ZZ"
    CATEGORY_EXPOSE_NUMBER = False
    id          = Column(Integer, primary_key=True)
    parent_id   = Column(Integer, ForeignKey('assets.id'))
    name        = Column(String, nullable=False)
    manufacturer = Column(String)
    model       = Column(String)
    custom_code = Column(Integer)
    note        = Column(Text)
    serial      = Column(String)

    # ARRAY was a great idea... 
    # ... except we can't do it in SQLite.
    if not TESTING:
        product_codes = Column(ARRAY(String))

    condition   = Column(Integer, default=0, nullable=False)
    functionality = Column(Integer, default=0, nullable=False)
    status      = Column(Enum(AssetStatus), default=AssetStatus.unknown, nullable=False)

    category = Column(Enum(AssetCategory), default=AssetCategory.unknown, nullable=False)

    location_id = Column(Integer, ForeignKey('locations.id'))
    #medium_id   = Column(Integer, ForeignKey('media.id'))
    hardware_type_id  = Column(Integer, ForeignKey('hardware_type.id'))

    children    = relationship("Asset", backref=backref("parent", remote_side=id))
    location    = relationship("Location", backref="assets")
    #medium      = relationship("Medium", backref="assets")
    hardware_type = relationship("HardwareType", backref="assets")

    transactions = relationship("Transaction", secondary='transaction_assets')

    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=True)
    organization = relationship("Organization")

    condition_new: AssetCondition = Column(Enum(AssetCondition), default=AssetCondition.unknown, nullable=False)  # type: ignore
    
    #producers = relationship(Company, backref="assets_produced")
    #distributors = relationship(Company, backref="assets_distributed")

    product_codes_new = relationship(ProductCode, backref="asset")

    platforms = relationship(Platform, secondary=asset_platform_table, backref="assets")
    tags      = relationship(AssetTag, secondary=asset_tag_table, backref="assets")

    __mapper_args__ = {
        "polymorphic_on": category
    }

    def __str__(self):
        return f"{self.code} {self.name}"
    
    @classmethod
    def get_free_custom_code(cls, category: AssetCategory):
        last_category_asset = db.session.query(cls) \
            .filter(cls.category == category, Asset.custom_code != None) \
            .order_by(desc(Asset.custom_code)).limit(1).scalar()

        if last_category_asset:
            return int(last_category_asset.custom_code) + 1

        return 1

    @property
    def code(self):
        string = ""
        if self.organization:
            string += f"{self.organization.shortname}: "

        if self.CATEGORY_EXPOSE_NUMBER:
            string += f"{self.CATEGORY_PREFIX}{self.custom_code}"
        else:
            if self.id is not None:
                string += f"{self.id:05}"
            else:
                string += "XXXXX"
        
        return string



    def get_primary_image(self):
        sorted_images = self.get_sorted_images()
        if sorted_images:
            return sorted_images[0]
        return None
    
    def get_sorted_images(self):
        return db.session.query(File) \
            .filter(
                File.asset_id==self.id, File.category.in_(IMAGE_CATEGORIES)
            ).order_by(File.primary.desc(), File.has_thumbnail.desc(), File.filepath.asc()).all()
    
    def get_dumps(self):
        return db.session.query(File) \
            .filter(
                File.asset_id==self.id, File.category == FileCategory.dump
            ).order_by(File.primary.desc(), File.filepath.asc()).all()

class AssetGame(Asset):
    CATEGORY_PREFIX = "GM"

    __mapper_args__ = {"polymorphic_identity": AssetCategory.game}

class AssetConsole(Asset):
    CATEGORY_PREFIX = "HK"
    CATEGORY_EXPOSE_NUMBER = True

    __mapper_args__ = {"polymorphic_identity": AssetCategory.console}
    

class AssetComputer(Asset):
    CATEGORY_PREFIX = "PC"
    CATEGORY_EXPOSE_NUMBER = True

    __mapper_args__ = {"polymorphic_identity": AssetCategory.computer}


class AssetConsoleAccesory(Asset):
    CATEGORY_PREFIX = "HP"

    __mapper_args__ = {"polymorphic_identity": AssetCategory.console_accesory}


class AssetComputerAccessory(Asset):
    CATEGORY_PREFIX = "PP"

    __mapper_args__ = {"polymorphic_identity": AssetCategory.computer_accessory}


class AssetComputerComponent(Asset):
    CATEGORY_PREFIX = "PK"
    CATEGORY_EXPOSE_NUMBER = True

    __mapper_args__ = {"polymorphic_identity": AssetCategory.computer_component}


class AssetComputerMouse(Asset):
    CATEGORY_PREFIX = "Myš"
    CATEGORY_EXPOSE_NUMBER = True

    __mapper_args__ = {"polymorphic_identity": AssetCategory.computer_mouse}


class AssetKeyboard(Asset):
    CATEGORY_PREFIX = "K"
    CATEGORY_EXPOSE_NUMBER = True

    __mapper_args__ = {"polymorphic_identity": AssetCategory.keyboard}


class AssetTelevision(Asset):
    CATEGORY_PREFIX = "TV"
    CATEGORY_EXPOSE_NUMBER = True

    __mapper_args__ = {"polymorphic_identity": AssetCategory.television}


class AssetMonitor(Asset):
    CATEGORY_PREFIX = "M"
    CATEGORY_EXPOSE_NUMBER = True

    __mapper_args__ = {"polymorphic_identity": AssetCategory.monitor}


class AssetSoftware(Asset):
    CATEGORY_PREFIX = "SW"

    __mapper_args__ = {"polymorphic_identity": AssetCategory.software}


class AssetMultimedia(Asset):
    CATEGORY_PREFIX = "MM"

    __mapper_args__ = {"polymorphic_identity": AssetCategory.multimedia}


class AssetReceipt(Asset):
    CATEGORY_PREFIX = "Receipt"

    __mapper_args__ = {"polymorphic_identity": AssetCategory.receipt}


class AssetLiterature(Asset):
    CATEGORY_PREFIX = "Lit"

    __mapper_args__ = {"polymorphic_identity": AssetCategory.literature}


class AssetOther(Asset):
    CATEGORY_PREFIX = "X"

    __mapper_args__ = {"polymorphic_identity": AssetCategory.other}


class AssetRewritableMedia(Asset):
    CATEGORY_PREFIX = "RWM"

    __mapper_args__ = {"polymorphic_identity": AssetCategory.rewritable_media}


class AssetMeta(db.Model):
    __tablename__ = 'assets_meta'
    id          = Column(Integer, primary_key=True)
    asset_id    = Column(Integer, ForeignKey('assets.id'))
    key         = Column(String, nullable=False)
    value       = Column(Text)

    asset       = relationship("Asset", backref="metadata")
