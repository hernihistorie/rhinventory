from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from rhinventory.api.asset.schemas import AssetSchema, AssetListOutputSchema
from rhinventory.api.database import get_db
from rhinventory.models.asset import Asset
from rhinventory.service.asset.services import AssetService

router = APIRouter()


@router.get("/get/{asset_id}")
def get_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = AssetService.get_single(db_session=db, asset_id=asset_id)
    if not asset:
        return {"error": "Asset not found"}

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
        assets=[AssetSchema(**asset_row._mapping) for asset_row in assets],
    )


@router.get("/list-by-tag", response_model=AssetListOutputSchema)
def list_assets_by_tag(tag_id: int, db: Session = Depends(get_db)):
    """
    List all public items by given tag.

    Has three parameters:
    * tag_id: Asset tag id.
    * limit: How many items to return.
    * offset: Offset in database query.

    """
    assets = AssetService.list_by_tag(db_session=db, tag_id=tag_id, private=False)

    return AssetListOutputSchema(
        assets=[AssetSchema(**asset_row._mapping) for asset_row in assets],
    )
