from enum import Enum
import json
from typing import Literal
import msgspec

from hhfloppy.event.events import HHFLOPPY_EVENT_CLASS_UNION, event_decoder as hhfloppy_event_decoder

from rhinventory.db import db
from rhinventory.events.event import RHINVENTORY_EVENT_CLASS_UNION, event_decoder as rhinventory_event_decoder
from rhinventory.models.events import DBEvent, EventSession, datetime

class EventNamespaceName(Enum):
    RHINVENTORY = "rhinventory"
    HHFLOPPY = "hhfloppy"

EVENT_CLASS_UNION = \
    RHINVENTORY_EVENT_CLASS_UNION | HHFLOPPY_EVENT_CLASS_UNION

SUPPORTED_EVENT_VERSION = 6

class UnsupportedEventVersion(Exception):
    pass

class EventStore():
    def __init__(self) -> None:
        pass

    @staticmethod
    def decode(event_data: bytes, namespace: EventNamespaceName) -> EVENT_CLASS_UNION:
        match namespace:
            case EventNamespaceName.RHINVENTORY:
                event = rhinventory_event_decoder.decode(event_data)
                assert isinstance(event, RHINVENTORY_EVENT_CLASS_UNION)
                return event
            case EventNamespaceName.HHFLOPPY:
                event = hhfloppy_event_decoder.decode(event_data)
                assert isinstance(event, HHFLOPPY_EVENT_CLASS_UNION)
                return event
            case _:
                raise ValueError(f"Unsupported namespace: {namespace}")

    def ingest(self, event: EVENT_CLASS_UNION, event_session: EventSession) -> None:
        if event.event_namespace != event_session.namespace:
            raise ValueError(
                f"Event namespace '{event.event_namespace}' does not match "
                f"event push key namespace '{event_session.namespace}'"
            )
        if event.event_version > SUPPORTED_EVENT_VERSION:
            raise UnsupportedEventVersion(
                f"Unsupported event version: {event.event_version}. "
            )

        db_event = DBEvent()
        # Note: We are trusting the event ID from the client here.
        db_event.id = event.event_id
        db_event.namespace = event.event_namespace
        db_event.class_name = event.__class__.__name__
        db_event.timestamp = event.event_timestamp
        db_event.ingested_at = datetime.now()
        db_event.event_session_id = event_session.id
        # XXX Here we are doing a encode-decode round-trip because we need the format
        # encoded by msgspec but SQLAlchemy needs a dict 
        db_event.data = json.loads(msgspec.json.encode(event))
        db.session.add(instance=db_event)
        db.session.commit()

event_store = EventStore()
