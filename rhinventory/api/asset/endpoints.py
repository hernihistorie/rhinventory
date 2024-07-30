from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from rhinventory.api.asset.schemas import AssetSchema
from rhinventory.api.database import get_db
from rhinventory.models.asset import Asset

router = APIRouter()


@router.get(path="/{asset_id}")
def get_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = db.query(Asset).get(asset_id)
    if not asset:
        return {"error": "Asset not found"}

    return {
        'id': asset.id,
        'category': asset.category.name,
        'name': asset.name
    }

@router.get("/list")
def list_assets():
    return [
        AssetSchema(
            id=1,
            name="Sample asset 1"
        ),
        AssetSchema(
            id=2,
            name="Sample asset 2"
        )
    ]