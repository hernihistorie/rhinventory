
import uuid
from rhinventory.events.event import Event


class FloppyDiskCaptureDisassociated(Event, kw_only=True, frozen=True):
    '''
        This floppy disk capture has been disassociated from an asset, possibly due to a mislabel.
    '''
    floppy_disk_capture_id: uuid.UUID
    reason_given: str | None = None
