import dataclasses

from flask import url_for
from sqlalchemy import select

from rhinventory.extensions import db
from rhinventory.models.file import File
from rhinventory.models.magdb import MagazineIssue, MagazineIssueVersion, MagazineIssueVersionPrice, \
    MagazineIssueVersionFiles, MagDBFileType, IssueStatus, Currency, MagazineSupplementVersion, MagazineSupplement


@dataclasses.dataclass
class PublicPrice:
    id: int
    value: float
    currency: Currency

@dataclasses.dataclass
class PublicFile:
    path: str
    thumbnail_path: str | None


@dataclasses.dataclass
class PublicSupplement:
    id: int
    title: str
    note: str
    status: IssueStatus
    confirmed: bool


@dataclasses.dataclass
class PublicVersion:
    id: int
    name_suffix: str
    status: IssueStatus
    prices: set[PublicPrice]
    cover_pages: list[PublicFile]
    index_pages: list[PublicFile]
    supplements: list[PublicSupplement]


@dataclasses.dataclass
class PublicIssue:
    id: int
    issue_number: int
    current_name: str
    published_day: int
    published_month: int
    published_year: int
    is_special_issue: bool
    versions: list[PublicVersion]


class PublicMagDBService:
    def list_magazine(self, magazine_id):
        issues = []

        issue_index = {}
        version_index = {}
        price_index = {}

        query = (
            select(
                MagazineIssue.id,
                MagazineIssue.issue_number,
                MagazineIssue.current_magazine_name,
                MagazineIssue.is_special_issue,
                MagazineIssue.published_day,
                MagazineIssue.published_month,
                MagazineIssue.published_year,
                MagazineIssueVersion.id,
                MagazineIssueVersion.name_suffix,
                MagazineIssueVersion.status,
                MagazineIssueVersionPrice.id,
                MagazineIssueVersionPrice.value,
                MagazineIssueVersionPrice.currency,
                MagazineIssueVersionFiles.file_type,
                File.id,
                File.filepath,
                File.has_thumbnail
            )
            .select_from(MagazineIssue)
            .where(MagazineIssue.magazine_id == magazine_id)
            .join(MagazineIssueVersion)
            .join(MagazineIssueVersionPrice, full=True)
            .join(MagazineIssueVersionFiles, full=True)
            .join(File, full=True)
            .order_by(
                MagazineIssue.published_year,
                MagazineIssue.published_month,
                MagazineIssue.published_day,
                MagazineIssue.issue_number,
                MagazineIssueVersion.name_suffix,
            )
        )

        for row in db.session.execute(query).fetchall():
            issue_id, issue_number, issue_name, is_special, pub_day, pub_month, pub_year,\
                version_id, name_suffix, version_status, \
                price_id, value, currency, \
                file_type, file_id, filepath, has_thumbnail = row
            try:
                issue = issue_index[issue_id]
            except KeyError:
                issue = PublicIssue(
                    id=issue_id,
                    is_special_issue=is_special,
                    issue_number=issue_number,
                    current_name=issue_name,
                    published_day=pub_day,
                    published_month=pub_month,
                    published_year=pub_year,
                    versions=[]
                )
                issue_index[issue_id] = issue
                issues.append(issue)

            try:
                version = version_index[version_id]
            except KeyError:
                version = PublicVersion(
                    id=version_id,
                    name_suffix=name_suffix,
                    status=version_status,
                    prices=[],
                    index_pages=[],
                    cover_pages=[],
                    supplements=[]
                )
                issue.versions.append(version)
                version_index[version_id] = version

            if value is not None and currency is not None:
                try:
                    price = price_index[price_id]
                except KeyError:
                    price = PublicPrice(
                        id=price_id,
                        value=value,
                        currency=currency
                    )
                    version.prices.append(price)
                    price_index[price_id] = price

            if file_type is not None:
                real_filepath = url_for('file', file_id=file_id, filename=filepath.split('/')[-1])

                if has_thumbnail:
                    thumbnail_path = url_for('file', file_id=file_id, filename=filepath.split('/')[-1], thumb=True)
                else:
                    thumbnail_path = None

                match file_type:
                    case MagDBFileType.index_page:
                        version.index_pages.append(PublicFile(
                            path=real_filepath,
                            thumbnail_path=thumbnail_path,
                        ))
                    case MagDBFileType.cover_page:
                        version.cover_pages.append(PublicFile(
                            path=real_filepath,
                            thumbnail_path=thumbnail_path,
                        ))

        supplements_query = (
            select(
                MagazineSupplement.id,
                MagazineSupplement.title,
                MagazineSupplement.note,
                MagazineSupplement.status,
                MagazineSupplement.confirmed,
                MagazineSupplementVersion.magazine_issue_version_id,
            ).join(MagazineSupplementVersion)
            .join(MagazineIssueVersion)
            .join(MagazineIssue)
            .where(MagazineIssue.magazine_id == magazine_id)
            .select_from(MagazineSupplement)
        )

        for row in db.session.execute(supplements_query).fetchall():
            supplement = PublicSupplement(
                id=row.id,
                title=row.title,
                note=row.note,
                status=IssueStatus(row.status),
                confirmed=row.confirmed
            )

            version_index[row.magazine_issue_version_id].supplements.append(supplement)

        return issues
