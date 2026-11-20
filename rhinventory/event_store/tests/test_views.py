import datetime
import json

import msgspec
import pytest

from rhinventory.db import User
from rhinventory.events.event import TestingEvent
from rhinventory.models.events import DBEvent, EventSession, PushKey

KEY = "pushkey_testtesttesttest"


@pytest.fixture()
def push_key(db_session) -> PushKey:
    """An authorized single-use push key, as hhfloppy gets one."""
    push_key = PushKey(
        key=KEY,
        uses_remaining=1,
        authorized_at=datetime.datetime.now(),
        authorized_by_user_id=db_session.query(User).first().id,
    )
    db_session.add(EventSession(application_name="hhfloppy", namespace="rhinventory", push_key=push_key))
    db_session.commit()
    return push_key


def push(client, events: list) -> tuple[int, dict]:
    serialized_events = [
        event if isinstance(event, dict) else json.loads(msgspec.json.encode(event))
        for event in events
    ]
    response = client.post("/event_store/ingest/", json={
        "namespace": "rhinventory",
        "key": KEY,
        "serialized_events": serialized_events,
    })
    return response.status_code, response.json


def stored_test_data(db_session) -> list[str]:
    return sorted(event.data["test_data"] for event in db_session.query(DBEvent))


def uses_remaining(db_session, push_key: PushKey) -> int | None:
    db_session.expire_all()
    return push_key.uses_remaining


def test_push_is_stored(client, db_session, push_key):
    status, body = push(client, [TestingEvent(test_data="a"), TestingEvent(test_data="b")])

    assert (status, body) == (200, {"status": "success", "ingested": 2, "duplicates": 0})
    assert stored_test_data(db_session) == ["a", "b"]
    assert uses_remaining(db_session, push_key) == 0


def test_failed_push_stores_nothing_and_can_be_retried(client, db_session, push_key):
    good = TestingEvent(test_data="good")

    status, _ = push(client, [good, {"type": "NoSuchEvent"}])
    assert status == 400
    assert stored_test_data(db_session) == []
    assert uses_remaining(db_session, push_key) == 1

    status, _ = push(client, [good])
    assert status == 200
    assert stored_test_data(db_session) == ["good"]


def test_retrying_a_stored_push_succeeds_without_using_the_key(client, db_session, push_key):
    events = [TestingEvent(test_data="a"), TestingEvent(test_data="b")]
    push(client, events)

    status, body = push(client, events)

    assert (status, body) == (200, {"status": "success", "ingested": 0, "duplicates": 2})
    assert stored_test_data(db_session) == ["a", "b"]
    assert uses_remaining(db_session, push_key) == 0


def test_spent_key_cant_push_new_events(client, db_session, push_key):
    stored = TestingEvent(test_data="stored")
    push(client, [stored])

    status, _ = push(client, [stored, TestingEvent(test_data="new")])

    assert status == 401
    assert stored_test_data(db_session) == ["stored"]


def test_reused_event_id_rejects_the_push(client, db_session, push_key):
    push_key.uses_remaining = 2
    db_session.commit()
    original = TestingEvent(test_data="original")
    push(client, [original])

    changed = msgspec.structs.replace(original, test_data="changed")
    status, body = push(client, [TestingEvent(test_data="new"), changed])

    assert status == 409
    assert body["event_id"] == str(original.event_id)
    assert stored_test_data(db_session) == ["original"]
    assert uses_remaining(db_session, push_key) == 1
