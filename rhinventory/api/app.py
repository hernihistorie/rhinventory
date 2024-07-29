from fastapi import FastAPI


def add_apis_routes(api: FastAPI):
    from rhinventory.api.asset.endpoints import router as asset_router
    api.include_router(asset_router, prefix='/asset')


app = FastAPI()
add_apis_routes(app)
