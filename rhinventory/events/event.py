import datetime
import uuid

import msgspec


class TaggedStruct(msgspec.Struct, kw_only=True, frozen=True, tag_field="type", tag=True):
    pass


class Event(TaggedStruct, kw_only=True, frozen=True):
    """Base class for events."""

    event_version: int = 6
    event_timestamp: datetime.datetime = msgspec.field(default_factory=datetime.datetime.now)
    event_namespace: str = "rhinventory"
    event_id: uuid.UUID = msgspec.field(default_factory=uuid.uuid7)


class TestingEvent(Event, kw_only=True, frozen=True):
    __test__ = False # prevent pytest from trying to collect this class
    test_id: uuid.UUID = msgspec.field(default_factory=uuid.uuid7)
    test_data: str

