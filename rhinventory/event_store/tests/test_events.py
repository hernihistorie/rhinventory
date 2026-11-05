import uuid

from flask_admin.tests.fileadmin import Flask
import pytest
import sqlalchemy.exc

from rhinventory.event_store.event_store import EventSession, UnsupportedEventVersion, event_store
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
        
