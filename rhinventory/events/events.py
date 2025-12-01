
import msgspec
from rhinventory.events.event import TestingEvent
from rhinventory.events.floppy_disk_captures import FloppyDiskCaptureDisassociated


RHINVENTORY_EVENT_CLASS_UNION = TestingEvent | FloppyDiskCaptureDisassociated

event_decoder = msgspec.json.Decoder(RHINVENTORY_EVENT_CLASS_UNION)
