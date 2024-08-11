from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from rhinventory.api.asset.schemas import AssetSchema, AssetListOutputSchema
from rhinventory.api.database import get_db
from rhinventory.models.asset import Asset
from rhinventory.service.asset.services import AssetService

router = APIRouter()


@router.get("/get/{asset_id}")
def get_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = db.query(Asset).get(asset_id)
    if not asset:
        return {"error": "Asset not found"}

    # TODO: Hide private

    return AssetSchema.model_validate(asset, from_attributes=True)


@router.get("/list-public", response_model=AssetListOutputSchema)
def list_assets(limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    """
    List all public items.

    Has two parameters:
    * limit: How many items to return.
    * offset: Offset in database query.
    """
    assets = AssetService.list_all(db, limit, offset, private=False)

    return AssetListOutputSchema(
        assets=[AssetSchema.model_validate(asset, from_attributes=True) for asset in assets],
    )


@router.get("/list-by-tag", response_model=AssetListOutputSchema)
def list_assets_by_tag(tag: str, db: Session = Depends(get_db)):
    """
    List all public items by given tag.

    Has three parameters:
    * tag: Asset tag. Must match exactly.
    * limit: How many items to return.
    * offset: Offset in database query.

    """
    assets = AssetService.list_by_tag(db, tag, private=False)

    return AssetListOutputSchema(
        assets=[AssetSchema.model_validate(asset, from_attributes=True) for asset in assets]
    )
