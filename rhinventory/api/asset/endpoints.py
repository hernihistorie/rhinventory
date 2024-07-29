from fastapi import APIRouter

from rhinventory.api.asset.schemas import AssetSchema

router = APIRouter()


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