"""Fix duplicate mediums and packagings

Revision ID: bc9d617547e6
Revises: 29fa77040244
Create Date: 2022-10-23 15:31:09.856746

"""
from alembic import op
import sqlalchemy as sa

from sqlalchemy import orm
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Packaging(Base):
    __tablename__ = 'packagings'
    id: int          = sa.Column(sa.Integer, primary_key=True)  # type: ignore
    name: str        = sa.Column(sa.String, nullable=False)  # type: ignore

class AssetPackaging(Base):
    __tablename__ = 'asset_packaging'
    id: int           = sa.Column(sa.Integer, primary_key=True)  # type: ignore
    packaging_id: int = sa.Column(sa.Integer, sa.ForeignKey(Packaging.id))  # type: ignore
    packaging = relationship(Packaging, backref="asset_packagings")

class Medium(Base):
    __tablename__ = 'media'
    id: int          = sa.Column(sa.Integer, primary_key=True)  # type: ignore
    name: str        = sa.Column(sa.String, nullable=False)  # type: ignore

class AssetMedium(Base):
    __tablename__ = 'asset_mediums'
    id: int           = sa.Column(sa.Integer, primary_key=True)  # type: ignore
    medium_id: int    = sa.Column(sa.Integer, sa.ForeignKey(Medium.id))  # type: ignore
    medium = relationship(Medium, backref="asset_mediums")


# revision identifiers, used by Alembic.
revision = 'bc9d617547e6'
down_revision = '29fa77040244'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    session = orm.Session(bind=bind)

    print("Fixing packagings")

    packaging_by_name = {}
    duplicate_packagings = []

    for packaging in session.query(Packaging).order_by(Packaging.id):
        lower_name = packaging.name.lower()
        if lower_name in packaging_by_name:
            #print(packaging.name, "dupe")
            fixed_packaging = packaging_by_name[lower_name]
            duplicate_packagings.append(packaging)
            for asset_packaging in packaging.asset_packagings:
                asset_packaging.packaging_id = fixed_packaging.id
        else:
            packaging_by_name[lower_name] = packaging
            #print(packaging.name)

    #print("Fixing mediums")

    mediums_by_name = {}
    duplicate_mediums = []

    for medium in session.query(Medium).order_by(Medium.id):
        lower_name = medium.name.lower()
        if lower_name in mediums_by_name:
            #print(medium.name, "dupe")
            fixed_medium = mediums_by_name[lower_name]
            duplicate_mediums.append(medium)
            for asset_medium in medium.asset_mediums:
                asset_medium.medium_id = fixed_medium.id
        else:
            mediums_by_name[lower_name] = medium
            #print(medium.name)
    
    #print("Committing")

    print("Deleting dupes")

    for duplicate in duplicate_packagings + duplicate_mediums:
        session.delete(duplicate)
    
    print("Committing")

    session.commit()
    pass


def downgrade():
    pass
