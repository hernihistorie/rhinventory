from contextlib import contextmanager
from enum import Enum
import json
from typing import Iterable, Iterator
from uuid import UUID
import msgspec
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from tqdm import tqdm

from flask_login import current_user

from hhfloppy.event.events import HHFLOPPY_EVENT_CLASS_UNION, event_decoder as hhfloppy_event_decoder, EVENT_VERSION as HHFLOPPY_EVENT_VERSION

from rhinventory.db import db
from rhinventory.events.events import RHINVENTORY_EVENT_CLASS_UNION, event_decoder as rhinventory_event_decoder
from rhinventory.models.aggregates.aggregate import Aggregate, registered_aggregate_classes
from rhinventory.models.events import DBEvent, EventSession, datetime
from rhinventory.models.log_transaction import current_log_transaction

class EventNamespaceName(Enum):
    RHINVENTORY = "rhinventory"
    HHFLOPPY = "hhfloppy"

EVENT_CLASS_UNION = \
    RHINVENTORY_EVENT_CLASS_UNION | HHFLOPPY_EVENT_CLASS_UNION

supported_event_version = HHFLOPPY_EVENT_VERSION

class UnsupportedEventVersion(Exception):
    pass

class ConflictingEvent(Exception):
    """An event with this id is already stored, with a different payload."""
    def __init__(self, event_id: UUID) -> None:
        super().__init__(f"Event {event_id} is already stored with a different payload")
        self.event_id = event_id

class EventStore():
    def __init__(self) -> None:
        pass

    @staticmethod
    def decode(event_data: bytes | dict, namespace: EventNamespaceName) -> EVENT_CLASS_UNION:
        if isinstance(event_data, dict):
            event_data = msgspec.json.encode(event_data)
        
        try:
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
        except msgspec.DecodeError as e:
            raise ValueError(f"Failed to decode event for namespace {namespace}: {e}\nFull event data: {event_data.decode('utf-8')}") from e
    
    def _apply_event_to_aggregates(self, event: EVENT_CLASS_UNION, aggregate_classes: Iterable[type[Aggregate]]) -> None:
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

    def rebuild_aggregates(
            self,
            aggregate_classes: Iterable[type[Aggregate]] | None = None,
            show_progress: bool = False) -> None:
        if aggregate_classes is None:
            aggregate_classes = registered_aggregate_classes
        for aggregate_class in aggregate_classes:
            db.session.query(aggregate_class).delete()

            class_names = [cls.__name__ for cls in aggregate_class.listen_for_event_classes]

            q = db.session.query(DBEvent) \
                .filter(DBEvent.class_name.in_(class_names)) \
                .order_by(DBEvent.ingested_at.asc())
            
            if show_progress:
                q = tqdm(q, desc=f"Rebuilding {aggregate_class.__name__}")
            
            for db_event in q:
                event_data = msgspec.json.decode(json.dumps(db_event.data))
                event = self.decode(
                    event_data=msgspec.json.encode(event_data),
                    namespace=EventNamespaceName(db_event.namespace)
                )

                self._apply_event_to_aggregates(event=event, aggregate_classes=[aggregate_class])
            db.session.commit()

    def ingest(self, event: EVENT_CLASS_UNION, event_session: EventSession) -> bool:
        """Store an event and apply it to the aggregates, without committing.

        Ingesting is idempotent: an event already stored with the same payload
        is skipped, and False returned.  If its payload differs, ConflictingEvent
        is raised and the caller should roll back.
        """
        if event.event_namespace != event_session.namespace:
            raise ValueError(
                f"Event namespace '{event.event_namespace}' does not match "
                f"event push key namespace '{event_session.namespace}'"
            )
        if event.event_version > supported_event_version:
            raise UnsupportedEventVersion(
                f"Unsupported event version: {event.event_version}. "
            )

        # XXX Here we are doing a encode-decode round-trip because we need the format
        # encoded by msgspec but SQLAlchemy needs a dict
        data = json.loads(msgspec.json.encode(event))

        log_transaction = current_log_transaction(db.session)
        db.session.flush()  # so a new event session and the log transaction have ids
        # Note: We are trusting the event ID from the client here.
        # Inserting with ON CONFLICT keeps concurrent pushes of the same event safe.
        inserted = db.session.execute(
            pg_insert(DBEvent.__table__).values(
                id=event.event_id,
                namespace=event.event_namespace,
                class_name=event.__class__.__name__,
                timestamp=event.event_timestamp,
                ingested_at=datetime.now(),
                event_session_id=event_session.id,
                log_transaction_id=log_transaction.id,
                data=data,
            ).on_conflict_do_nothing(index_elements=["id"]).returning(DBEvent.__table__.c.id)
        ).first()

        if inserted is None:
            stored_data = db.session.execute(
                select(DBEvent.__table__.c.data).where(DBEvent.__table__.c.id == event.event_id)
            ).scalar_one()
            if stored_data != data:
                raise ConflictingEvent(event.event_id)
            return False

        self._apply_event_to_aggregates(event=event, aggregate_classes=registered_aggregate_classes)
        return True

    @contextmanager
    def event_session_for_current_user(
        self,
        application_name: str = "rhinventory",
        namespace: str = "rhinventory"
    ) -> Iterator["EventSessionContext"]:
        """Create an event session context manager for the current user.

        The session and its events are committed together when the block
        exits, or rolled back if it raises.

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

        context = EventSessionContext(event_store=self, event_session=event_session)
        try:
            yield context
        except BaseException:
            db.session.rollback()
            raise
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
    
    def ingest(self, event: EVENT_CLASS_UNION) -> bool:
        """Ingest an event using this session, see EventStore.ingest."""
        return self._event_store.ingest(event=event, event_session=self._event_session)


event_store = EventStore()
