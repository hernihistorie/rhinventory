from rhinventory.app import create_app
from rhinventory.event_store.event_store import EventStore
app = create_app()
with app.app_context():
    print("Rebuilding aggregates...")
    event_store = EventStore()
    event_store.rebuild_aggregates()
    print("Done.")
