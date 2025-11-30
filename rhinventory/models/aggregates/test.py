from typing import Union
from uuid import uuid7
from sqlalchemy.orm import Mapped, mapped_column

from rhinventory.events.event import TestingEvent
from rhinventory.models.aggregates.aggregate import Aggregate

class TestAggregate(Aggregate):
    __test__ = False # prevent pytest from trying to collect this class
    __tablename__ = 'agg_test_aggregates'
    listen_for_events_type = Union[TestingEvent]
    listen_for_event_classes = frozenset({TestingEvent})

    latest_test_event_data: Mapped[str | None] = mapped_column()

    @classmethod
    def filter_from_event(cls, event: listen_for_events_type) -> bool:
        match event:
            case TestingEvent():
                return True
            case _:
                raise ValueError(f"Unsupported event type: {type(event)}")

    def __init__(self) -> None:
        super().__init__()
        self.id = uuid7()

    def apply_event(self, event: listen_for_events_type) -> None:
        self.last_event_id = event.event_id
        match event:
            case TestingEvent():
                self.latest_test_event_data = event.test_data
            case _:
                raise ValueError(f"Unsupported event type: {type(event)}")

