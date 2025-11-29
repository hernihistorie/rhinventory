import uuid

import pytest
import sqlalchemy.exc

from rhinventory.event_store.event_store import EventSession, UnsupportedEventVersion, event_store
from rhinventory.events.event import TestingEvent
from rhinventory.extensions import db

def test_event_creation(app):
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
