import datetime

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_utils.expressions import ColumnElement

from rhinventory.events.statements import StatementCreated, StatementDeleted, AssetID
from rhinventory.models.aggregates.aggregate import Aggregate, registered_aggregate_class
from rhinventory.models.properties.property import PropertyID


@registered_aggregate_class
class Statement(Aggregate):
    __tablename__ = 'agg_statements'
    listen_for_events_type = StatementCreated | StatementDeleted
    listen_for_event_classes = frozenset({StatementCreated, StatementDeleted})

    subject_id: Mapped[AssetID | None] = mapped_column(index=True, nullable=True)
    property_id: Mapped[PropertyID | None] = mapped_column(nullable=True)
    value: Mapped[str | None] = mapped_column(nullable=True)
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)

    @classmethod
    def filter_from_event(cls, event: StatementCreated | StatementDeleted) -> ColumnElement[bool]:
        match event:
            case StatementDeleted():
                return cls.id == event.statement_id
            case StatementCreated():
                return cls.id == event.event_id

    def apply_event(self, event: StatementCreated | StatementDeleted) -> None:
        match event:
            case StatementDeleted():
                self.deleted_at = event.event_timestamp
            case StatementCreated():
                self.id = event.event_id
                self.last_event_id = event.event_id
                self.subject_id = event.subject_id
                self.property_id = event.property_id
                self.value = event.value
