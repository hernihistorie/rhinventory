from typing import Any
from uuid import UUID

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_utils.expressions import ColumnElement

from hhfloppy.event.events import Event

from rhinventory.extensions import db

# TODO make abstract
class Aggregate(db.Model):
    __abstract__ = True
    rhinventory_log = False
    
    listen_for_events_type = Any
    listen_for_event_classes: frozenset[type[Any]] = frozenset({})

    id: Mapped[UUID] = mapped_column(primary_key=True)
    last_event_id: Mapped[UUID | None] = mapped_column()

    @classmethod
    def filter_from_event(cls, event: listen_for_events_type) -> ColumnElement[bool] | bool:
        raise NotImplementedError()

    def apply_event(self, event: listen_for_events_type) -> None:
        raise NotImplementedError()

registered_aggregate_classes: list[type[Aggregate]] = []
def registered_aggregate_class(cls: type[Aggregate]) -> type[Aggregate]:
    registered_aggregate_classes.append(cls)
    return cls
