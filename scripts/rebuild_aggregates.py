from rhinventory.app import create_app
from rhinventory.models.aggregates.floppy_disk_capture import FloppyDiskCapture
from rhinventory.event_store.event_store import EventStore
app = create_app()
with app.app_context():
    event_store = EventStore()
    event_store.rebuild_aggregates()
