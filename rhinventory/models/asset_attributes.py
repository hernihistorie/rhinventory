import sys
import enum

from sqlalchemy import Column, DateTime, Integer, String, ForeignKey, Table
from sqlalchemy.orm import relationship, backref

from rhinventory.extensions import db

class SimpleAssetAttribute():
    name: str
    def __str__(self) -> str:
        return f"{self.name}"

def asset_n_to_n_table(other_table: db.Model) -> Table:
    other_name = other_table.__name__.lower()
    return Table(
        f"asset_{other_name}",
        db.Model.metadata,
        Column("asset_id", ForeignKey("assets.id")),
        Column(f"{other_name}_id", ForeignKey(other_table.id)),
    )

class Platform(db.Model, SimpleAssetAttribute):
    __tablename__ = 'platforms'
    id: int          = Column(Integer, primary_key=True)  # type: ignore
    slug: str        = Column(String, nullable=False)  # type: ignore
    name: str        = Column(String, nullable=False)  # type: ignore

asset_platform_table = asset_n_to_n_table(Platform)

class AssetTag(db.Model, SimpleAssetAttribute):
    __tablename__ = 'tags'
    id: int          = Column(Integer, primary_key=True)  # type: ignore
    name: str        = Column(String, nullable=False)  # type: ignore

asset_tag_table = asset_n_to_n_table(AssetTag)

class Packaging(db.Model, SimpleAssetAttribute):
    __tablename__ = 'packagings'
    id: int          = Column(Integer, primary_key=True)  # type: ignore
    name: str        = Column(String, nullable=False)  # type: ignore

# An asset can have a single packaging multiple times so we need a middle table
class AssetPackaging(db.Model):
    __tablename__ = 'asset_packaging'
    id: int           = Column(Integer, primary_key=True)  # type: ignore
    asset_id: int     = Column(Integer, ForeignKey('assets.id'))  # type: ignore
    packaging_id: int = Column(Integer, ForeignKey(Packaging.id))  # type: ignore

    #asset = relationship("Asset")
    #packaging = relationship(Packaging)

class Medium(db.Model, SimpleAssetAttribute):
    __tablename__ = 'media'
    id: int          = Column(Integer, primary_key=True)  # type: ignore
    name: str        = Column(String, nullable=False)  # type: ignore

class AssetMedium(db.Model):
    __tablename__ = 'asset_mediums'
    id: int           = Column(Integer, primary_key=True)  # type: ignore
    asset_id: int     = Column(Integer, ForeignKey('assets.id'))  # type: ignore
    medium_id: int    = Column(Integer, ForeignKey(Medium.id))  # type: ignore

    #asset = relationship("Asset")
    #medium = relationship(Medium)

class Company(db.Model, SimpleAssetAttribute):
    __tablename__ = 'companies'
    id: int          = Column(Integer, primary_key=True)  # type: ignore
    name: str        = Column(String, nullable=False)  # type: ignore
    last_used        = Column(DateTime, nullable=True)

class CompanyAlias(db.Model):
    __tablename__ = 'company_aliases'
    id: int          = Column(Integer, primary_key=True)  # type: ignore
    alias: str       = Column(String, nullable=False)  # type: ignore
    company_id = Column(Integer, ForeignKey(Company.id), nullable=False)
    company = relationship(Company, backref="aliases")

asset_company_table = asset_n_to_n_table(Company)
