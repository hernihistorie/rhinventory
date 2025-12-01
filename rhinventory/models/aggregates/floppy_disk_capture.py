from datetime import datetime
from typing import Union
from uuid import UUID
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Relationship, mapped_column, relationship

from hhfloppy.event.events import FloppyDiskCaptureDirectoryConverted, FloppyDiskCaptureSummarized
from sqlalchemy_utils.expressions import ColumnElement

from rhinventory.db import Asset
from rhinventory.models.aggregates.aggregate import Aggregate

class FloppyDiskCapture(Aggregate):
    __tablename__ = 'agg_floppy_disk_captures'
    listen_for_events_type = Union[FloppyDiskCaptureDirectoryConverted, FloppyDiskCaptureSummarized]
    listen_for_event_classes = frozenset({FloppyDiskCaptureDirectoryConverted, FloppyDiskCaptureSummarized})

    latest_pyhxcfe_run_id: Mapped[UUID | None] = mapped_column()
    asset_id: Mapped[int | None] = mapped_column() # don't use foregin key because we don't want a hard constraint
    dumped_at: Mapped[datetime | None] = mapped_column()
    operator_name: Mapped[str | None] = mapped_column()
    directory_name: Mapped[str | None] = mapped_column()
    drive_name: Mapped[str | None] = mapped_column()
    converted: Mapped[bool | None] = mapped_column()
    formats: Mapped[list[str] | None] = mapped_column(JSONB)

    number_of_tracks: Mapped[int | None] = mapped_column()
    number_of_sides: Mapped[int | None] = mapped_column()
    has_errors: Mapped[bool | None] = mapped_column()
    error_count: Mapped[int | None] = mapped_column()
    parsing_errors: Mapped[int | None] = mapped_column()

    asset: Relationship[Asset | None] = relationship(foreign_keys=[asset_id], primaryjoin="FloppyDiskCapture.asset_id==Asset.id")

    @classmethod
    def filter_from_event(cls, event: listen_for_events_type) -> ColumnElement[bool]:
        match event:
            case FloppyDiskCaptureDirectoryConverted():
                return cls.id == event.floppy_disk_capture_id
            case FloppyDiskCaptureSummarized():
                return cls.id == event.floppy_disk_capture_id
            case _:
                raise ValueError(f"Unsupported event type: {type(event)}")


    def apply_event(self, event: listen_for_events_type) -> None:
        self.id = event.floppy_disk_capture_id
        self.last_event_id = event.event_id
        match event:
            case FloppyDiskCaptureDirectoryConverted():
                self.latest_pyhxcfe_run_id = event.pyhxcfe_run_id
                self.converted = True
                self.formats = event.formats
                self.directory_name = event.floppy_disk_capture_directory
            case FloppyDiskCaptureSummarized():
                self.latest_pyhxcfe_run_id = event.pyhxcfe_run_id
                self.directory_name = event.floppy_disk_capture_directory
                # parse a date like 2025-10-03_16-52-51
                self.dumped_at = datetime.strptime(event.name_info.datetime, "%Y-%m-%d_%H-%M-%S")
                self.operator_name = event.name_info.operator
                self.drive_name = event.name_info.drive
                if event.name_info.hh_asset_id:
                    self.asset_id = event.name_info.hh_asset_id
                self.number_of_tracks = event.xml_info.number_of_tracks
                self.number_of_sides = event.xml_info.number_of_sides
                self.error_count = event.imd_info.error_count

                self.has_errors = bool(self.error_count or self.parsing_errors)
            case _:
                raise ValueError(f"Unsupported event type: {type(event)}")
