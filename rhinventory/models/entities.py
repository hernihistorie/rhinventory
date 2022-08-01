from sqlalchemy import Column, Integer, String, Text, \
    ForeignKey, Boolean
from sqlalchemy.orm import relationship, backref

from rhinventory.extensions import db


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
        return self.name or self.legal_name or self.email


class Country(db.Model):
    __tablename__ = 'countries'
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    code = Column(String(16))

    def __str__(self):
        return self.code
