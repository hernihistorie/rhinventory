import csv
import dataclasses
from enum import StrEnum

from rhinventory.app import create_app
from rhinventory.extensions import db
from rhinventory.models.magdb import Magazine, MagazineIssue, MagazineIssueVersion

csv_file = "/Users/rainbow/Desktop/BasicScore.csv"

class CSVIssueStatus(StrEnum):
    have = "have"
    dont_have = "dont_have"
    problem = "problems"
    not_confirmed = "not confirmed"

@dataclasses.dataclass
class CSVIssueVersion:
    suffix: str
    comment: str
    status: CSVIssueStatus

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

with open(csv_file) as f:
    reader = csv.reader(f)

    resulting_data = []

    for row in reader:
        versions = []

        if row[2] != "x":
            issue = CSVIssueVersion(
                suffix="Standart",
                comment="",
                status=get_status(row[2])
            )
            versions.append(issue)

        if row[3] != "x":
            issue = CSVIssueVersion(
                suffix="CD",
                comment="",
                status=get_status(row[3])
            )
            versions.append(issue)

        if row[4] != "x":
            issue = CSVIssueVersion(
                suffix="DVD",
                comment="",
                status=get_status(row[4])
            )
            versions.append(issue)

        if row[5] != "x":
            issue = CSVIssueVersion(
                suffix="karton",
                comment="",
                status=get_status(row[5])
            )
            versions.append(issue)

        if row[6] != "x":
            issue = CSVIssueVersion(
                suffix="Steam hra",
                comment="seznam her: " + row[7],
                status=get_status(row[6])
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
        db_issue = MagazineIssue(
            issue_number=issue.issue_number,
            current_magazine_name=issue.title.capitalize(),
            is_special_issue=False,
            magazine_id=magazine.id,
            note=issue.comment,
        )
        db.session.add(db_issue)


        for version in issue.versions:
            db_version = MagazineIssueVersion(
                magazine_issue=db_issue,
                name_suffix=version.suffix,
                confirmed=True if version.status != CSVIssueStatus.not_confirmed else False,
                status=version.status if version.status != CSVIssueStatus.not_confirmed else "dont_have",
                note=version.comment
            )
            db.session.add(db_version)

        print(f"Issue num {issue.issue_number} added.")
    db.session.commit()