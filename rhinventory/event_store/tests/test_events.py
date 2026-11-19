import uuid

from flask import Flask
import pytest
import sqlalchemy.exc

from rhinventory.event_store.event_store import EventSession, UnsupportedEventVersion, event_store
from rhinventory.models.aggregates.statement import Statement
from rhinventory.models.aggregates.test import TestAggregate
from rhinventory.events.event import TestingEvent
from rhinventory.extensions import db

def test_event_creation(app: Flask) -> None:
    with app.app_context():
        test_event_session = EventSession()
        test_event_session.application_name = "test_events.py"
        test_event_session.namespace = "rhinventory"
        test_event_session.internal = True
        db.session.add(test_event_session)
        db.session.commit()

        test_data = "Sample test data"
        event = TestingEvent(test_data=test_data)

        assert event.test_data == test_data
        assert isinstance(event.event_id, uuid.UUID)
        assert hasattr(event, 'event_timestamp')

        event_store.ingest(event=event, event_session=test_event_session)

        with pytest.raises(sqlalchemy.exc.IntegrityError):
            event_store.ingest(event=event, event_session=test_event_session)
        
        db.session.rollback()
        
        # TestingAggregate should have been created/updated
        aggregate_instance = db.session.query(TestAggregate).one_or_none()
        assert aggregate_instance is not None
        assert aggregate_instance.latest_test_event_data == test_data

        # Test rebuilding aggregates
        event_store.rebuild_aggregates(aggregate_classes=[TestAggregate])
        aggregate_instance_after_rebuild = db.session.query(TestAggregate).one_or_none()
        assert aggregate_instance_after_rebuild is not None
        assert aggregate_instance_after_rebuild.latest_test_event_data == test_data


def test_rebuild_only_applies_events_to_rebuilt_aggregate(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    """Rebuilding one aggregate must not replay its events into other aggregates
    listening for the same event classes, as those weren't cleared first."""
    consulted = []

    def spy_filter_from_event(cls, event):
        consulted.append(event)
        return False

    monkeypatch.setattr(Statement, 'listen_for_event_classes', frozenset({TestingEvent}))
    monkeypatch.setattr(Statement, 'filter_from_event', classmethod(spy_filter_from_event))

    with app.app_context():
        test_event_session = EventSession()
        test_event_session.application_name = "test_events.py"
        test_event_session.namespace = "rhinventory"
        test_event_session.internal = True
        db.session.add(test_event_session)
        db.session.commit()

        event_store.ingest(event=TestingEvent(test_data="data"), event_session=test_event_session)
        assert len(consulted) == 1  # ingesting applies to all listening aggregates

        event_store.rebuild_aggregates(aggregate_classes=[TestAggregate])
        assert len(consulted) == 1
