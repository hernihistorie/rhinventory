import csv
import dataclasses
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from rhinventory.app import create_app
from rhinventory.extensions import db
from rhinventory.models.magdb import Magazine, MagazineIssue, MagazineIssueVersion, IssueStatus, MagazineSupplement, \
    MagazineSupplementVersion

csv_file = "/home/rainbow/projects/personal/rhinventory/basic-score.csv"

class CSVIssueStatus(StrEnum):
    have = "have"
    dont_have = "dont_have"
    problem = "problems"
    not_confirmed = "not confirmed"


@dataclasses.dataclass
class CSVSupplement:
    title: str
    note: str
    status: CSVIssueStatus


@dataclasses.dataclass
class CSVIssueVersion:
    suffix: str
    comment: str
    status: CSVIssueStatus
    supplements: list[CSVSupplement]

@dataclasses.dataclass
class CSVIssue:
    title: str
    issue_number: int
    versions: list[CSVIssueVersion]
    comment: str


def get_status(status):
    match status:
        case "1":
            return CSVIssueStatus.have
        case "0":
            return CSVIssueStatus.dont_have
        case "p":
            return CSVIssueStatus.problem
        case "?":
            return CSVIssueStatus.not_confirmed


def get_db_status(status):
    match status:
        case CSVIssueStatus.have:
            return IssueStatus.have
        case CSVIssueStatus.problem:
            return IssueStatus.problems
        case CSVIssueStatus.not_confirmed:
            return IssueStatus.dont_have
        case CSVIssueStatus.dont_have:
            return IssueStatus.dont_have


with open(csv_file) as f:
    reader = csv.reader(f)

    resulting_data = []

    for row in reader:
        versions = []
        supplements = []

        # supplements
        if row[5] != "x":
            supplement = CSVSupplement(
                title="Karton",
                note="",
                status=get_status(row[5])
            )

            for version in versions:
                supplements.append(supplement)

        if row[6] != "x":
            supplement = CSVSupplement(
                title="Steam hry",
                note="seznam her: " + row[7],
                status=get_status(row[6])
            )

            for version in versions:
                supplements.append(supplement)

        # issues
        if row[2] != "x":
            issue = CSVIssueVersion(
                suffix="standard",
                comment="",
                status=get_status(row[2]),
                supplements=supplements
            )
            versions.append(issue)

        if row[3] != "x":
            issue = CSVIssueVersion(
                suffix="CD",
                comment="",
                status=get_status(row[3]),
                supplements=supplements

            )
            versions.append(issue)

        if row[4] != "x":
            issue = CSVIssueVersion(
                suffix="DVD",
                comment="",
                status=get_status(row[4]),
                supplements=supplements
            )
            versions.append(issue)

        issue = CSVIssue(
            title=row[0],
            issue_number=row[1],
            versions=versions,
            comment=row[8]
        )
        resulting_data.append(issue)

app = create_app()

with app.app_context():

    magazine = db.session.query(Magazine).get(3)

    for issue in resulting_data:
        db_query = insert(MagazineIssue).values(
            issue_number=issue.issue_number,
            current_magazine_name=issue.title.capitalize(),
            is_special_issue=False,
            magazine_id=magazine.id,
            note=issue.comment,
        ).on_conflict_do_nothing().returning(MagazineIssue.id)
        result = db.session.execute(db_query)

        magazine_id = result.fetchone()

        if magazine_id is None:
            query = select(MagazineIssue.id).where(
                MagazineIssue.issue_number==issue.issue_number,
                MagazineIssue.magazine_id==magazine.id
            )

            magazine_id = db.session.execute(query).fetchone()

        for version in issue.versions:
            db_version = MagazineIssueVersion(
                magazine_issue_id=magazine_id[0],
                name_suffix=version.suffix,
                confirmed=True if version.status != CSVIssueStatus.not_confirmed else False,
                status=get_db_status(version.status),
                note=version.comment
            )
            db.session.add(db_version)

            for supplement in version.supplements:
                supplement_db = MagazineSupplement(
                    title=supplement.title,
                    note=supplement.note,
                    confirmed=True if supplement.status != CSVIssueStatus.not_confirmed else False,
                    status=get_db_status(supplement.status)
                )
                db.session.add(supplement_db)

                connection = MagazineSupplementVersion(
                    magazine_supplement_id=supplement_db.id,
                    magazine_issue_version_id=db_version.id,
                )
                db.session.add(connection)

        print(f"Issue num {issue.issue_number} added.")
    db.session.commit()