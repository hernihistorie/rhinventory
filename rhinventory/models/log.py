import json
import datetime
import enum
import typing

import flask_login
from sqlalchemy import Boolean, Column, Integer, Numeric, String, Text, \
    DateTime, ForeignKey, Enum, Index, inspect, event
from sqlalchemy.orm import relationship, object_mapper, ColumnProperty, RelationshipProperty
from sqlalchemy.orm.attributes import History, get_history
from sqlalchemy.orm.base import NO_VALUE, PASSIVE_NO_INITIALIZE, PassiveFlag

from rhinventory.extensions import db
from rhinventory.db import User
from rhinventory.models.events import DBEvent

LogEvent = enum.Enum('LogEvent', ["Create", "Update", "Delete", "Other"])

class LogItem(db.Model):
    __tablename__ = 'logs'
    id          = Column(Integer, primary_key=True)
    
    table       = Column(String(80), nullable=False)
    object_id   = Column(Integer, nullable=False)
    event       = Column(Enum(LogEvent), nullable=False)
    object_json = Column(Text)
    object_json_new_format = Column(Boolean)
    
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

    if isinstance(obj, DBEvent):
        # don't log events: they are read-only, additionally their ids are uuids and not integers,
        # which is incompatible with the current log table schema.
        return

    if getattr(obj, "rhinventory_log", True) is False:
        # object has logging disabled
        return

    user_id = None
    if flask_login.current_user and flask_login.current_user.is_authenticated:
        user_id = flask_login.current_user.id
    db.session.add(
        LogItem(
            table=type(obj).__name__,
            object_id=obj.id,
            event=event,
            object_json=json.dumps(
                data,
                default=repr,
                ensure_ascii=False),
            object_json_new_format=True,
            user_id=user_id,
            datetime=datetime.datetime.now(),
            extra_json="{}"
        )
    )


def _logs_collection_changes(prop: RelationshipProperty) -> bool:
    """Whether changes to this many-to-many collection are logged on its owner.

    Of two relationships kept in sync by a backref (`Asset.tags` and
    `AssetTag.assets`), only the one declaring the backref is logged, so each
    change is logged once.  Changes made through the other side are still
    logged, as SQLAlchemy mirrors them onto the declaring side.
    """
    if prop.secondary is None or prop.viewonly:
        return False
    if prop.backref is not None or prop.back_populates is None:
        return True
    reverse = prop.mapper.relationships[prop.back_populates]
    if reverse.backref is not None:
        return False
    # Declared with back_populates on both sides, so pick one
    return (prop.parent.class_.__name__, prop.key) < (reverse.parent.class_.__name__, reverse.key)


def _ids(objects: typing.Iterable[typing.Any]) -> list[typing.Any]:
    return sorted(obj.id for obj in objects)


def _collection_history(obj: typing.Any, key: str) -> History:
    """Changes made to a collection, without loading it.

    Includes changes that reached an unloaded collection through a backref,
    which SQLAlchemy keeps as pending mutations.
    """
    return get_history(obj, key, passive=PASSIVE_NO_INITIALIZE | PassiveFlag.INCLUDE_PENDING_MUTATIONS)


@event.listens_for(db.session, 'after_flush')
def receive_after_flush(session, flush_context):
    """The hook for saving changes in DB.

    Logs the columns of created objects, the changed columns of updated ones,
    and everything still loaded of deleted ones.  Many-to-many collections are
    logged as lists of ids on create and delete, and as `{"added": [...],
    "removed": [...]}` on update.
    """
    for obj in session.new:
        if isinstance(obj, LogItem):  # ignore LogItem objects
            continue

        data = {}
        for mapper_property in object_mapper(obj).iterate_properties:
            if isinstance(mapper_property, ColumnProperty):
                key = mapper_property.key
                attribute_state = inspect(obj).attrs.get(key)
                data[key] = attribute_state.value
            elif isinstance(mapper_property, RelationshipProperty) and _logs_collection_changes(mapper_property):
                data[mapper_property.key] = _ids(_collection_history(obj, mapper_property.key).added)

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
            elif isinstance(mapper_property, RelationshipProperty) and _logs_collection_changes(mapper_property):
                history = _collection_history(obj, mapper_property.key)
                if history.added or history.deleted:
                    changes[mapper_property.key] = {
                        "added": _ids(history.added),
                        "removed": _ids(history.deleted),
                    }

        # Objects can be dirty without any logged change, e.g. through the
        # other side of a backref, which is logged on the declaring side.
        if changes:
            log_data(obj, "Update", changes)

    for obj in session.deleted:
        if isinstance(obj, LogItem):  # ignore LogItem objects
            continue

        # Record what's gone, including all many-to-many links, which the
        # delete removed without them being logged anywhere else.
        data = {}
        for mapper_property in object_mapper(obj).iterate_properties:
            if isinstance(mapper_property, ColumnProperty) or (
                    isinstance(mapper_property, RelationshipProperty)
                    and mapper_property.secondary is not None and not mapper_property.viewonly):
                value = inspect(obj).attrs[mapper_property.key].loaded_value
                if value is NO_VALUE:
                    continue
                data[mapper_property.key] = _ids(value) if isinstance(mapper_property, RelationshipProperty) else value

        log_data(obj, "Delete", data)