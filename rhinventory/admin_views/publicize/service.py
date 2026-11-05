from dataclasses import dataclass

from sqlalchemy import ColumnElement, and_, or_
from sqlalchemy.orm import selectinload

from rhinventory.db import Asset
from rhinventory.extensions import db
from rhinventory.models.asset_attributes import AssetTag
from rhinventory.models.enums import Privacy
from rhinventory.models.file import File


@dataclass
class PublicizeItem:
    asset: Asset
    images: list[File]
    other_files: list[File]


@dataclass
class SaveResult:
    assets_changed: int = 0
    files_changed: int = 0


def find_tag(requested: str) -> AssetTag | None:
    """Find a tag by ID, falling back to its name, since names aren't unique and can be numeric."""
    tag = None
    try:
        tag = db.session.get(AssetTag, int(requested))
    except ValueError:
        pass
    if tag:
        return tag
    return db.session.query(AssetTag).filter(AssetTag.name == requested).order_by(AssetTag.id).first()


def _needs_judging() -> ColumnElement[bool]:
    """Unjudged assets, and judged ones with unjudged files, such as newly uploaded ones."""
    return or_(
        Asset.privacy == Privacy.private_implicit,
        Asset.files.any(and_(
            File.privacy == Privacy.private_implicit,
            or_(File.is_deleted == False, File.is_deleted == None),
        )),
    )


def get_progress() -> tuple[int, int]:
    """The number of assets that need judging, and of all assets."""
    needs_judging = db.session.query(Asset).filter(_needs_judging()).count()
    return needs_judging, db.session.query(Asset).count()


def get_queue(start_id: int, count: int, tag: AssetTag | None) -> list[PublicizeItem]:
    """The next assets that need judging, with their non-deleted files."""
    query = db.session.query(Asset).options(selectinload(Asset.files)).filter(
        _needs_judging(),
        Asset.id >= start_id,
    )
    if tag:
        query = query.filter(Asset.tags.any(AssetTag.id == tag.id))

    items = []
    for asset in query.order_by(Asset.id.asc()).limit(count):
        files = asset._sorted_files
        items.append(PublicizeItem(
            asset=asset,
            images=[file for file in files if file.is_image],
            other_files=[file for file in files if not file.is_image],
        ))
    return items


def apply_decisions(
    asset_decisions: dict[int, Privacy | None],
    file_decisions: dict[int, Privacy | None],
    publicize_blanks: bool,
) -> SaveResult:
    """Apply a reviewer's decisions, without committing.  None is a blank decision.

    Nothing changes unless it was on the reviewer's page, which is why decisions only ever reach
    the files in `file_decisions`, and never soft-deleted ones:

    - An explicit decision always wins.
    - With `publicize_blanks`, a blank asset becomes public.
    - A blank file follows its asset's decision, if there is one.
    - A blank never overrides an earlier decision, such as one made while the page was open.
    """
    result = SaveResult()
    inherited: dict[int, Privacy] = {}

    for asset in db.session.query(Asset).filter(Asset.id.in_(list(asset_decisions))):
        decision = asset_decisions[asset.id]
        if decision is None and publicize_blanks and asset.privacy == Privacy.private_implicit:
            decision = Privacy.public
        if decision is None:
            continue

        inherited[asset.id] = decision
        if asset.privacy != decision:
            asset.privacy = decision
            result.assets_changed += 1

    files = db.session.query(File).filter(
        File.id.in_(list(file_decisions)),
        or_(File.is_deleted == False, File.is_deleted == None),
    )
    for file in files:
        decision = file_decisions[file.id]
        if decision is None and file.privacy == Privacy.private_implicit:
            decision = inherited.get(file.asset_id)

        if decision is not None and file.privacy != decision:
            file.privacy = decision
            result.files_changed += 1

    return result
