import uuid

from rhinventory.events.event import Event

AssetID = int
PropertyID = uuid.UUID


class StatementCreated(Event, kw_only=True, frozen=True):
    """A statement about this property of an asset has been asserted."""
    subject_id: AssetID
    property_id: PropertyID
    value: str
