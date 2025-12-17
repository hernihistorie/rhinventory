from typing import Union
from uuid import UUID, uuid5

from sqlalchemy import ColumnElement
from sqlalchemy.orm import Mapped, mapped_column

from hhfloppy.event.events import FileConverted

from rhinventory.models.aggregates.aggregate import Aggregate, registered_aggregate_class

# Namespace UUID for generating deterministic file aggregate IDs from hashes
FILE_AGGREGATE_NAMESPACE = UUID('019b2d03-29c4-7f94-85a2-2ee4742ae712')

def blake3_to_file_aggregate_id(blake3_hash: str) -> UUID:
    """Generate a deterministic UUID for a FileAggregate based on its BLAKE3 hash."""
    return uuid5(FILE_AGGREGATE_NAMESPACE, blake3_hash)

@registered_aggregate_class
class FileAggregate(Aggregate):
    __tablename__ = 'agg_files'
    listen_for_events_type = Union[FileConverted]
    listen_for_event_classes = frozenset({FileConverted})

    last_known_filename: Mapped[str | None] = mapped_column()

    hash_md5: Mapped[bytes | None] = mapped_column()
    hash_sha256: Mapped[bytes | None] = mapped_column()
    hash_blake3: Mapped[bytes | None] = mapped_column()

    file_conversion_id: Mapped[UUID | None] = mapped_column()

    # derived_from_file_id: Mapped[UUID | None] = mapped_column(ForeignKey('agg_files.id'))
    # derived_from_file: Mapped["FileAggregate | None"] = relationship(
    #     remote_side="FileAggregate.id",
    #     foreign_keys=[derived_from_file_id]
    # )

    @classmethod
    def filter_from_event(cls, event: listen_for_events_type) -> ColumnElement[bool] | bool:
        match event:
            case FileConverted():
                return cls.hash_blake3 == bytes.fromhex(event.output_file_metadata.checksums.blake3)
            case _:
                raise ValueError(f"Unsupported event type: {type(event)}")

    def apply_event(self, event: listen_for_events_type) -> None:
        self.last_event_id = event.event_id
        match event:
            case FileConverted():
                self.id = blake3_to_file_aggregate_id(event.output_file_metadata.checksums.blake3)
                self.last_known_filename = event.output_file_metadata.filename
                self.hash_md5 = bytes.fromhex(event.output_file_metadata.checksums.md5)
                self.hash_sha256 = bytes.fromhex(event.output_file_metadata.checksums.sha256)
                self.hash_blake3 = bytes.fromhex(event.output_file_metadata.checksums.blake3)
                self.file_conversion_id = event.file_conversion_id
            case _:
                raise ValueError(f"Unsupported event type: {type(event)}")
