from pydantic import BaseModel


class AssetSchema(BaseModel):
    id: int
    name: str
