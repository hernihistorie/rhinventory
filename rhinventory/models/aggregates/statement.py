from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_utils.expressions import ColumnElement

from rhinventory.events.statements import StatementCreated, AssetID, PropertyID
from rhinventory.models.aggregates.aggregate import Aggregate, registered_aggregate_class


@registered_aggregate_class
class Statement(Aggregate):
    __tablename__ = 'agg_statements'
    listen_for_events_type = StatementCreated
    listen_for_event_classes = frozenset({StatementCreated})

    subject_id: Mapped[AssetID] = mapped_column(index=True)
    property_id: Mapped[PropertyID] = mapped_column()
    value: Mapped[str] = mapped_column()

    @classmethod
    def filter_from_event(cls, event: StatementCreated) -> ColumnElement[bool]:
        return cls.id == event.event_id

    def apply_event(self, event: StatementCreated) -> None:
        self.id = event.event_id
        self.last_event_id = event.event_id
        self.subject_id = event.subject_id
        self.property_id = event.property_id
        self.value = event.value
