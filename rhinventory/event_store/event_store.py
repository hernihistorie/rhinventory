from contextlib import contextmanager
from enum import Enum
import json
from typing import Iterable, Iterator
import msgspec

from flask_login import current_user

from hhfloppy.event.events import HHFLOPPY_EVENT_CLASS_UNION, event_decoder as hhfloppy_event_decoder

from rhinventory.db import db
from rhinventory.events.events import RHINVENTORY_EVENT_CLASS_UNION, event_decoder as rhinventory_event_decoder
from rhinventory.models.aggregates.aggregate import Aggregate
from rhinventory.models.aggregates.floppy_disk_capture import FloppyDiskCapture
from rhinventory.models.aggregates.test import TestAggregate
from rhinventory.models.events import DBEvent, EventSession, datetime

class EventNamespaceName(Enum):
    RHINVENTORY = "rhinventory"
    HHFLOPPY = "hhfloppy"

EVENT_CLASS_UNION = \
    RHINVENTORY_EVENT_CLASS_UNION | HHFLOPPY_EVENT_CLASS_UNION

SUPPORTED_EVENT_VERSION = 7

class UnsupportedEventVersion(Exception):
    pass

class EventStore():
    aggregate_classes: list[type[Aggregate]] = [TestAggregate, FloppyDiskCapture]

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
    
    def _apply_event_to_aggregates(self, event: EVENT_CLASS_UNION, aggregate_classes: list[type[Aggregate]]) -> None:
        for aggregate_class in aggregate_classes:
            if type(event) in aggregate_class.listen_for_event_classes:
                filter_expr = aggregate_class.filter_from_event(event)
                if isinstance(filter_expr, bool) and filter_expr is False:
                    continue

                q = db.session.query(aggregate_class)
                if filter_expr is not True:
                    q = q.filter(filter_expr)

                aggregate_instance = q.one_or_none()

                if aggregate_instance is None:
                    aggregate_instance = aggregate_class()
                    aggregate_instance.apply_event(event)
                    db.session.add(aggregate_instance)
                else:
                    aggregate_instance.apply_event(event)

    def rebuild_aggregates(self, aggregate_classes: Iterable[type[Aggregate]] | None = None) -> None:
        if aggregate_classes is None:
            aggregate_classes = self.aggregate_classes
        for aggregate_class in aggregate_classes:
            db.session.query(aggregate_class).delete()

            class_names = [cls.__name__ for cls in aggregate_class.listen_for_event_classes]

            q = db.session.query(DBEvent) \
                .filter(DBEvent.class_name.in_(class_names)) \
                .order_by(DBEvent.ingested_at.asc())
            
            for db_event in q:
                event_data = msgspec.json.decode(json.dumps(db_event.data))
                event = self.decode(
                    event_data=msgspec.json.encode(event_data),
                    namespace=EventNamespaceName(db_event.namespace)
                )

                self._apply_event_to_aggregates(event=event, aggregate_classes=[aggregate_class])
            db.session.commit()

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

        self._apply_event_to_aggregates(event=event, aggregate_classes=self.aggregate_classes)

        db.session.commit()

    @contextmanager
    def event_session_for_current_user(
        self,
        application_name: str = "rhinventory",
        namespace: str = "rhinventory"
    ) -> Iterator["EventSessionContext"]:
        """Create an event session context manager for the current user.
        
        Usage:
            with event_store.event_session_for_current_user() as event_session:
                event_session.ingest(some_event)
        """
        event_session = EventSession()
        event_session.application_name = application_name
        event_session.namespace = namespace
        event_session.internal = True
        event_session.user_id = current_user.id
        db.session.add(event_session)
        db.session.commit()
        
        context = EventSessionContext(event_store=self, event_session=event_session)
        try:
            yield context
        finally:
            event_session.closed = True
            db.session.commit()


class EventSessionContext:
    """Context wrapper for EventSession that provides an ingest method."""
    
    def __init__(self, event_store: EventStore, event_session: EventSession) -> None:
        self._event_store = event_store
        self._event_session = event_session
    
    @property
    def event_session(self) -> EventSession:
        return self._event_session
    
    def ingest(self, event: EVENT_CLASS_UNION) -> None:
        """Ingest an event using this session."""
        self._event_store.ingest(event=event, event_session=self._event_session)


event_store = EventStore()
