from datetime import datetime
import sys
import enum
from typing import TYPE_CHECKING, Self

from sqlalchemy import Column, Integer, String, Text, \
    DateTime, ForeignKey, Enum, \
        ARRAY, desc, or_
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Relationship, relationship, Mapped, mapped_column

from rhinventory.models.computers import HardwareType
if TYPE_CHECKING:
    from rhinventory.db import FloppyDiskCapture, Organization
else:
    FloppyDiskCapture = "FloppyDiskCapture"
from rhinventory.models.asset_attributes import Company, Platform, Medium, Packaging, AssetTag, asset_tag_table, asset_platform_table, asset_company_table
from rhinventory.models.enums import Privacy

from rhinventory.models.file import File, IMAGE_CATEGORIES, FileCategory
from rhinventory.extensions import db
from rhinventory.models.transaction import Transaction
from rhinventory.util import slugify

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
    packaging = 17
    location = 18

ASSET_CATEGORY_PREFIXES: dict[AssetCategory, str] = {
    AssetCategory.unknown: "UNK",
    AssetCategory.game: "GM",
    AssetCategory.console: "HK",
    AssetCategory.computer: "PC",
    AssetCategory.console_accesory: "HP",
    AssetCategory.computer_accessory: "PP",
    AssetCategory.computer_component: "PK",
    AssetCategory.computer_mouse: "Myš",
    AssetCategory.keyboard: "K",
    AssetCategory.television: "TV",
    AssetCategory.monitor : "M",
    AssetCategory.software : "SW",
    AssetCategory.multimedia : "MM",
    AssetCategory.receipt : "Receipt",
    AssetCategory.literature : "Lit",
    AssetCategory.other : "X",
    AssetCategory.rewritable_media: "RWM",
    AssetCategory.packaging: "PKG",
    AssetCategory.location: "Loc"
}
EXPOSED_CATEGORY_NUMBERS: set[AssetCategory] = {
    AssetCategory.console, AssetCategory.computer,
    AssetCategory.computer_mouse, AssetCategory.keyboard,
    AssetCategory.television, AssetCategory.monitor,
}

class Asset(db.Model):
    __tablename__ = 'assets'

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey('assets.id'))
    name: Mapped[str] = mapped_column(String, nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String)  # TODO remove
    model: Mapped[str | None] = mapped_column(String)
    custom_code: Mapped[int | None] = mapped_column()
    note: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    serial: Mapped[str | None] = mapped_column(String)

    product_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    condition: Mapped[int] = mapped_column(default=0, nullable=False)
    functionality: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[AssetStatus] = mapped_column(Enum(AssetStatus), default=AssetStatus.unknown, nullable=False)

    category: Mapped[AssetCategory] = mapped_column(Enum(AssetCategory), default=AssetCategory.unknown, nullable=False)

    location_id: Mapped[int | None] = mapped_column(ForeignKey('locations.id'))
    location_id_new: Mapped[int | None] = mapped_column(ForeignKey('assets.id'))
    #medium_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('media.id'))
    hardware_type_id: Mapped[int | None] = mapped_column( ForeignKey('hardware_type.id'))

    children: Relationship[list[Asset] | None] = relationship("Asset", foreign_keys=[parent_id], back_populates="parent")
    parent: Relationship[Asset | None] = relationship("Asset", foreign_keys=[parent_id], remote_side=[id], back_populates="children")

    contains: Relationship[list[Asset] | None] = relationship("Asset", foreign_keys=[location_id_new], back_populates="location")
    location: Relationship[Asset | None] = relationship("Asset", foreign_keys=[location_id_new], remote_side=[id], back_populates="children")
    #medium = relationship("Medium", backref="assets")
    hardware_type: Relationship[HardwareType | None] = relationship(HardwareType, backref="assets")

    transactions: Relationship[list[Transaction] | None] = relationship(Transaction, secondary='transaction_assets')

    organization_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('organizations.id'), nullable=True)
    organization:  Relationship["Organization | None"] = relationship("Organization")

    condition_new: Mapped[AssetCondition] = mapped_column(Enum(AssetCondition), default=AssetCondition.unknown, nullable=False)

    _privacy: Mapped[Privacy] = mapped_column('privacy', Enum(Privacy), default=Privacy.private_implicit, nullable=False)

    created_at: Mapped[datetime | None] = mapped_column(nullable=True)
    made_public_at: Mapped[datetime | None] = mapped_column(nullable=True)
    #producers = relationship(Company, backref="assets_produced")
    #distributors = relationship(Company, backref="assets_distributed")

    platforms: Relationship[list[Platform] | None] = relationship(Platform, secondary=asset_platform_table, backref="assets")
    tags: Relationship[list[AssetTag] | None] = relationship(AssetTag, secondary=asset_tag_table, backref="assets")
    mediums: Relationship[list[Medium] | None] = relationship(Medium, secondary='asset_mediums', backref="assets")
    packaging: Relationship[list[Packaging] | None] = relationship(Packaging, secondary='asset_packaging', backref="assets")
    companies: Relationship[list[Company] | None] = relationship(Company, secondary=asset_company_table, backref="assets")
    floppy_disk_captures: Relationship[list[FloppyDiskCapture] | None] = relationship("FloppyDiskCapture", primaryjoin="foreign(FloppyDiskCapture.asset_id)==Asset.id")

    LAST_USED_ATTRIBUTES: dict[str, type] = {
        'platforms': Platform,
        'tags': AssetTag,
        'mediums': Medium,
        'packaging': Packaging,
        'companies': Company,
    }

    def __str__(self) -> str:
        return f"{self.code} {self.name}"

    @property
    def slug(self) -> str:
        return slugify(self.name)

    @property
    def url(self) -> str:
        import flask
        if self.slug:
            return flask.url_for('asset.details_view', id=self.id, slug=self.slug)
        else:
            return flask.url_for('asset.details_view', id=self.id)

    @property
    def CATEGORY_PREFIX(self) -> str:
        return ASSET_CATEGORY_PREFIXES[self.category]

    @property
    def CATEGORY_EXPOSE_NUMBER(self) -> bool:
        return self.category in EXPOSED_CATEGORY_NUMBERS
    
    @classmethod
    def get_free_custom_code(cls, category: AssetCategory) -> int:
        last_category_asset = db.session.query(cls) \
            .filter(cls.category == category, Asset.custom_code != None) \
            .order_by(desc(Asset.custom_code)).limit(1).scalar()

        if last_category_asset:
            return int(last_category_asset.custom_code) + 1

        return 1

    @property
    def code(self) -> str:
        string = ""
        if self.organization:
            string += f"{self.organization.shortname}: "

        string += self.code_without_organization
        
        return string

    @property
    def code_without_organization(self) -> str:
        string = ""
        if self.CATEGORY_EXPOSE_NUMBER:
            string += f"{self.CATEGORY_PREFIX}{self.custom_code}"
        else:
            if self.id is not None:
                string += f"{self.id:05}"
            else:
                string += "XXXXX"
        
        return string

    @hybrid_property
    def privacy(self) -> Privacy:
        return self._privacy

    @privacy.setter
    def privacy(self, value: Privacy) -> None:
        if self._privacy != Privacy.public and value == Privacy.public:
            self.made_public_at = datetime.utcnow()

        self._privacy = value


    def get_primary_image(self):
        return self.get_sorted_images().first()
        
    @property
    def _query_files(self):
        return db.session.query(File) \
            .filter(
                or_(File.is_deleted == False, File.is_deleted == None),
                File.asset_id==self.id
            ).order_by(File.primary.desc(), File.has_thumbnail.desc(), File.filepath.asc())

    def get_files_in_categories(self, categories: list[FileCategory]):
        return self._query_files \
            .filter(
                File.category.in_(categories)
            )
    
    def get_sorted_images(self):
        return self.get_files_in_categories(IMAGE_CATEGORIES)

    def get_primary_dump(self):
        return self.get_dumps().first()
    
    def get_dumps(self):
        return self.get_files_in_categories([FileCategory.dump])

    def get_primary_document(self):
        return self.get_files_in_categories([FileCategory.document]).first()

    @property
    def parents(self) -> list[Asset]:
        parents: list[Asset] = []
        parent = self.parent
        while parent:
            parents.append(parent)
            parent = parent.parent

        return list(reversed(parents))

    @property
    def locations(self) -> list[Asset]:
        parents: list[Asset] = []
        parent = self.location
        while parent:
            parents.append(parent)
            parent = parent.parent

        return list(reversed(parents))

class AssetMeta(db.Model):
    __tablename__ = 'assets_meta'
    id          = Column(Integer, primary_key=True)
    asset_id    = Column(Integer, ForeignKey('assets.id'))
    key         = Column(String, nullable=False)
    value       = Column(Text)

    asset       = relationship("Asset", backref="metadata")
