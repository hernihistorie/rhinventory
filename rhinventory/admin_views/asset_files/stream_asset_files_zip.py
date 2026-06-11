from typing import Iterable
import os
from datetime import datetime
from stat import S_IFREG
from dataclasses import dataclass

from stream_zip import ZIP_AUTO, stream_zip

from rhinventory.db import Asset, File

@dataclass
class AssetZipMember:
    zip_name: str
    filepath: str
    size: int
    modified_at: datetime


def stream_asset_files_zip(assets: Iterable[Asset]) -> Iterable[bytes]:
    # Gather all member names and paths up front; file contents are only
    # read lazily while the zip is being streamed out.
    members: list[AssetZipMember] = []
    for asset in assets:
        used_names: set[str] = set()
        for file in asset.files:
            assert isinstance(file, File)
            if file.is_deleted or not os.path.exists(file.full_filepath):
                continue
            name = file.filename
            if name in used_names:
                if '.' in name:
                    stem, ext = name.rsplit('.', 1)
                    name = f"{stem}_{file.id}.{ext}"
                else:
                    name = f"{name}_{file.id}"
            used_names.add(name)
            members.append(AssetZipMember(
                zip_name=f"hh{asset.id}/{name}",
                filepath=file.full_filepath,
                size=os.path.getsize(file.full_filepath),
                modified_at=file.upload_date or datetime.now(),
            ))

    mode = S_IFREG | 0o644

    def file_contents(filepath: str) -> Iterable[bytes]:
        with open(filepath, 'rb') as f:
            while chunk := f.read(65536):
                yield chunk

    def member_files():
        for member in members:
            yield member.zip_name, member.modified_at, mode, ZIP_AUTO(member.size), file_contents(member.filepath)

    return stream_zip(member_files())