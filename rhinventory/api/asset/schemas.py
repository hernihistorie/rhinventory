from typing import List

from pydantic import BaseModel


class AssetSchema(BaseModel):
    id: int
    name: str
    model: str | None
    note: str | None
    serial: str | None


class AssetListOutputSchema(BaseModel):
    assets: List[AssetSchema]
