from typing import TypedDict

from flask import url_for
import markdown
from markupsafe import Markup
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from rhinventory.extensions import db
from rhinventory.db import Asset, File, IMAGE_CATEGORIES
from rhinventory.models.asset_attributes import AssetTag
from rhinventory.models.enums import PUBLIC_PRIVACIES


# Files without a thumbnail can only be shown as they are, which rules out formats like TIFF
BROWSER_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp')


class PublicSearchAsset(TypedDict):
    id: int
    slug: str
    name: str
    code: str
    product_codes: list[str]
    serial: str | None
    description: str | None
    note: str | None
    model: str | None
    tags: list[str]
    companies: list[str]
    platforms: list[str]
    mediums: list[str]
    image: str | None


class PublicSearchTag(TypedDict):
    id: int
    name: str
    description: str | None
    url: str | None
    list_path: str
    is_featured: bool
    is_collection: bool
    is_project: bool
    is_post: bool


class PublicSearchData(TypedDict):
    assets: list[PublicSearchAsset]
    tags: list[PublicSearchTag]


def markdown_to_text(text: str | None) -> str | None:
    if not text:
        return None
    return Markup(markdown.markdown(text)).striptags()


def get_primary_image_paths() -> dict[int, str]:
    """Paths of the images to show for assets, respecting the privacy of files."""
    files = db.session.execute(
        select(File.asset_id, File.id, File.filepath, File.has_thumbnail)
        .where(
            File.asset_id != None,
            File.category.in_(IMAGE_CATEGORIES),
            File.privacy.in_(PUBLIC_PRIVACIES),
            or_(File.is_deleted == False, File.is_deleted == None),
        )
        .order_by(File.asset_id, File.primary.desc(), File.has_thumbnail.desc(), File.filepath.asc())
    )

    paths: dict[int, str] = {}
    for asset_id, file_id, filepath, has_thumbnail in files:
        if asset_id in paths:
            continue
        if has_thumbnail:
            paths[asset_id] = f'/files/{file_id}/thumb'
        elif filepath.lower().endswith(BROWSER_IMAGE_EXTENSIONS):
            paths[asset_id] = f'/files/{file_id}'
    return paths


def get_public_search_data() -> PublicSearchData:
    """Everything public that herniarchiv.cz makes searchable.  It builds its search
    index from this, so nothing hidden from visitors may end up here."""
    public_assets = Asset.privacy.in_(PUBLIC_PRIVACIES)
    assets = db.session.scalars(
        select(Asset)
        .where(public_assets)
        .options(
            selectinload(Asset.tags),
            selectinload(Asset.companies),
            selectinload(Asset.platforms),
            selectinload(Asset.mediums),
        )
        .order_by(Asset.id)
    )
    # The list of tags is for staff only, so don't reveal those of hidden assets
    tags = db.session.scalars(
        select(AssetTag).where(AssetTag.assets.any(public_assets)).order_by(AssetTag.id)
    )
    image_paths = get_primary_image_paths()

    return {
        'assets': [
            {
                'id': asset.id,
                'slug': asset.slug,
                'name': asset.name,
                'code': asset.code_without_organization,
                'product_codes': asset.product_codes or [],
                'serial': asset.serial,
                'description': markdown_to_text(asset.description),
                'note': asset.note,
                'model': asset.model,
                'tags': [tag.name for tag in asset.tags],
                'companies': [company.name for company in asset.companies],
                'platforms': [platform.name for platform in asset.platforms],
                'mediums': [medium.name for medium in asset.mediums],
                'image': image_paths.get(asset.id),
            }
            for asset in assets
        ],
        'tags': [
            {
                'id': tag.id,
                'name': tag.name,
                'description': tag.description,
                'url': tag.url,
                'list_path': url_for('asset.index_view', flt1_45=tag.name),
                'is_featured': tag.is_featured,
                'is_collection': tag.is_collection,
                'is_project': tag.is_project,
                'is_post': tag.is_post,
            }
            for tag in tags
        ],
    }
