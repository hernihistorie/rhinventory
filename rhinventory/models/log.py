import json
import datetime
import enum

from sqlalchemy import Column, Integer, Numeric, String, Text, \
    DateTime, LargeBinary, ForeignKey, Enum, Table, Index, Boolean, CheckConstraint
from sqlalchemy.orm import relationship, backref

from rhinventory.extensions import db
from rhinventory.db import User

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
        event=event, object_json=json.dumps(object.asdict(), default=repr, ensure_ascii=False) if log_object else None,
        user_id=user.id if user else None,
        datetime=datetime.datetime.now(),
        extra_json=json.dumps(kwargs, ensure_ascii=False))
    db.session.add(log_item)
