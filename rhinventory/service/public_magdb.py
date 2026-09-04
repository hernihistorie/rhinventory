from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from rhinventory.extensions import db
from rhinventory.models.magdb import (
    MagazineIssue,
    MagazineIssueVersion,
    MagazineIssueVersionFiles,
    MagazineSupplementVersion,
)


class PublicMagDBService:
    def list_magazine(self, magazine_id: int) -> list[MagazineIssue]:
        """All issues of a magazine, in publication order, with everything the public
        templates render loaded up front.

        Which of the loaded fields actually end up public is decided by the templates
        rendering these, see magdb/magazine_detail.yaml.jinja2.
        """
        query = (
            select(MagazineIssue)
            # an issue without a single version is an incomplete record, keep it unpublished
            .where(MagazineIssue.magazine_id == magazine_id, MagazineIssue.versions.any())
            .options(
                joinedload(MagazineIssue.issuer),
                selectinload(MagazineIssue.versions).options(
                    selectinload(MagazineIssueVersion.prices),
                    selectinload(MagazineIssueVersion.files)
                        .joinedload(MagazineIssueVersionFiles.file),
                    selectinload(MagazineIssueVersion.supplements)
                        .joinedload(MagazineSupplementVersion.magazine_supplement),
                ),
            )
            .order_by(
                MagazineIssue.published_year,
                MagazineIssue.published_month,
                MagazineIssue.published_day,
                MagazineIssue.issue_number,
            )
        )

        return list(db.session.scalars(query))
