import uuid

from rhinventory.events.event import Event
from rhinventory.models.properties.property import PropertyID

type AssetID = int


class StatementCreated(Event, kw_only=True, frozen=True):
    """A statement about this property of an asset has been asserted."""
    subject_id: AssetID
    property_id: PropertyID
    value: str


class StatementDeleted(Event, kw_only=True, frozen=True):
    """A previously asserted statement has been retracted."""
    statement_id: uuid.UUID
