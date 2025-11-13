from sqlalchemy import Column, Integer, Numeric, String, Text, \
    DateTime, LargeBinary, ForeignKey, Enum, Table, Index, Boolean, CheckConstraint, func
from sqlalchemy.orm import relationship, backref

from rhinventory.extensions import db
from rhinventory.models.entities import Party
from rhinventory.models.label_printer import LabelPrinter

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

    party_id = Column(Integer, ForeignKey('parties.id'))
    party = relationship(Party)

    organization_id = Column(Integer, ForeignKey('organizations.id'))
    organization = relationship("Organization", backref=backref("users", order_by=id))

    label_printer_id = Column(Integer, ForeignKey(LabelPrinter.id))
    label_printer = relationship(LabelPrinter)

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


class AnynomusUser(User):
    username = "_anonymous"
    read_access = False
    write_access = False
    admin = False
    
    @property
    def is_authenticated(self):
        return False
    
    @property
    def is_active(self):
        return False
    
    @property
    def is_anonymous(self):
        return True


# Unused 2025-11-03
# class UserBookmark(db.Model):
#     __tablename__ = 'user_bookmarks'
#
#     id = Column(Integer, primary_key=True)
#     user_id = Column(Integer, ForeignKey('users.id'))
#     user: User = relationship(User)
#
#     created_at = Column(DateTime, server_default=func.now())
#     asset_id = Column(Integer, ForeignKey('assets.id'))
#     asset = relationship("Asset")
#
#     is_bookmarked = Column(Boolean)
#     bookmarked_at = Column(DateTime)
#
#     user_note = Column(Text)
    
