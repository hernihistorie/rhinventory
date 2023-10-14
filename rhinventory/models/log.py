import json
import datetime
import enum
import typing

import flask_login
from sqlalchemy import Column, Integer, Numeric, String, Text, \
    DateTime, ForeignKey, Enum, Index, inspect, event
from sqlalchemy.orm import relationship, object_mapper, ColumnProperty

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

def log(event: LogEvent, object: typing.Any, log_object=True, user: User | None=None, **kwargs) -> None:
    log_item = LogItem(
        table=type(object).__name__,
        object_id=object.id,
        event=event,
        object_json=json.dumps(object.asdict(), default=repr, ensure_ascii=False) if log_object else None,
        user_id=user.id if user else None,
        datetime=datetime.datetime.now(),
        extra_json=json.dumps(kwargs, ensure_ascii=False)
    )
    db.session.add(log_item)


def log_data(obj: typing.Any, event: str, data: dict[typing.Any, typing.Any]) -> None:
    """Create LogItem object and save it to database, tailored for hook bellow.

    :param obj: SQLAlchemy object from Session (data from current session)
    :param event: str, that is converted to LogEvent column
    :param data: dict with data, that are saved to object_json column
    """
    db.session.add(
        LogItem(
            table=type(obj).__name__,
            object_id=obj.id,
            event=event,
            object_json=json.dumps(
                data,
                default=repr,
                ensure_ascii=False),
            user_id=flask_login.current_user.id if flask_login.current_user else None,
            datetime=datetime.datetime.now(),
            extra_json="{}"
        )
    )


@event.listens_for(db.session, 'after_flush')
def receive_after_flush(session, flush_context):
    """The hook for saving changes in DB."""
    for obj in session.new:
        if isinstance(obj, LogItem):  # ignore LogItem objects
            continue

        data = {}
        for mapper_property in object_mapper(obj).iterate_properties:
            if isinstance(mapper_property, ColumnProperty):
                key = mapper_property.key
                attribute_state = inspect(obj).attrs.get(key)
                data[key] = attribute_state.value

        log_data(obj, "Create", data)

    changed_objects = session.new.union(session.dirty)
    for obj in changed_objects:
        if isinstance(obj, LogItem):  # ignore LogItem objects
            continue

        changes = {}
        if not inspect(obj).persistent:
            continue

        for mapper_property in object_mapper(obj).iterate_properties:
            if isinstance(mapper_property, ColumnProperty):
                key = mapper_property.key
                attribute_state = inspect(obj).attrs.get(key)
                history = attribute_state.history

                if history.has_changes():
                    value = attribute_state.value
                    changes[key] = value

        log_data(obj, "Update", changes)

    for obj in session.deleted:
        if isinstance(obj, LogItem):  # ignore LogItem objects
            continue

        log_data(obj, "Delete", {})