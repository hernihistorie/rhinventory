from typing import List, Tuple, Any

from pydantic import BaseModel

from rhinventory.models.asset import Asset


class AssetSchema(BaseModel):
    id: int
    name: str
    model: str | None
    note: str | None
    serial: str | None
    primary_image_path: str | None
    primary_document_path: str | None
    primary_dump_path: str | None



class AssetListOutputSchema(BaseModel):
    assets: List[AssetSchema]
