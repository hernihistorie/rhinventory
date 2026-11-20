import uuid

from flask import Flask
from flask_login import login_user
import msgspec
import pytest

from rhinventory.db import User
from rhinventory.event_store.event_store import ConflictingEvent, EventSession, event_store
from rhinventory.models.events import DBEvent
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

        assert event_store.ingest(event=event, event_session=test_event_session)
        db.session.commit()

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
        db.session.commit()
        assert len(consulted) == 1  # ingesting applies to all listening aggregates

        event_store.rebuild_aggregates(aggregate_classes=[TestAggregate])
        assert len(consulted) == 1


def make_event_session(db_session) -> EventSession:
    event_session = EventSession(application_name="test_events.py", namespace="rhinventory", internal=True)
    db_session.add(event_session)
    db_session.commit()
    return event_session


def test_ingesting_a_stored_event_again_is_skipped(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    event_session = make_event_session(db_session)
    event = TestingEvent(test_data="once")
    assert event_store.ingest(event=event, event_session=event_session)
    db_session.commit()

    applied = []
    monkeypatch.setattr(TestAggregate, "apply_event", lambda self, event: applied.append(event))
    assert not event_store.ingest(event=event, event_session=event_session)
    db_session.commit()

    assert applied == []
    assert db_session.query(DBEvent).count() == 1


def test_ingesting_a_different_event_with_a_stored_id_conflicts(db_session) -> None:
    event_session = make_event_session(db_session)
    event = TestingEvent(test_data="original")
    event_store.ingest(event=event, event_session=event_session)
    db_session.commit()

    with pytest.raises(ConflictingEvent) as excinfo:
        event_store.ingest(event=msgspec.structs.replace(event, test_data="changed"), event_session=event_session)
    assert excinfo.value.event_id == event.event_id
    db_session.rollback()

    assert db_session.query(TestAggregate).one().latest_test_event_data == "original"


def test_event_session_for_current_user_commits_together(client, db_session) -> None:
    with client.application.test_request_context():
        login_user(db_session.query(User).first())
        with event_store.event_session_for_current_user() as event_session:
            event_session.ingest(TestingEvent(test_data="committed"))

        with pytest.raises(RuntimeError):
            with event_store.event_session_for_current_user() as event_session:
                event_session.ingest(TestingEvent(test_data="rolled back"))
                raise RuntimeError("the command failed")

    db_session.expire_all()
    assert db_session.query(EventSession).one().closed
    assert [event.data["test_data"] for event in db_session.query(DBEvent)] == ["committed"]
