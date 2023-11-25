import enum

import flask_login
from sqlalchemy import func, UniqueConstraint

from rhinventory.extensions import db
from rhinventory.models.user import User


def get_current_user_id():
    """Get's current looged in user."""
    try:
        return flask_login.current_user.id
    except AttributeError:
        result = User.query.where(User.username=="robot").first()

        if result is not None:
            return result.id
        return None


class HistoryTrait(db.Model):
    __abstract__ = True
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.TIMESTAMP, server_default=func.now(), onupdate=func.current_timestamp())
    created_by = db.Column(db.Integer, default=get_current_user_id)
    updated_by = db.Column(db.Integer, default=get_current_user_id, onupdate=get_current_user_id)


class CheckedTrait(db.Model):
    __abstract__ = True
    inserted = db.Column(db.Boolean, server_default="False")
    manually_checked = db.Column(db.Boolean, server_default="False")


class Issuer(HistoryTrait):
    __tablename__ = "issuers"
    id = db.Column(db.Integer(), unique=True, primary_key=True)
    title = db.Column(db.String(255), info={"label": "Jméno vydavatele"})

    def __str__(self):
        return self.title


class Magazine(HistoryTrait):
    __tablename__ = "magazines"
    id = db.Column(db.Integer(), unique=True, primary_key=True)
    title = db.Column(db.String(255), unique=True, info={"label": "Název časopisu"})
    description = db.Column(db.Text(), default="", info={"label": "Popis"})
    country_id = db.Column(db.Integer, db.ForeignKey('countries.id'), nullable=True)

    def __str__(self):
        return self.title

    def get_logos(self):
        return [file for file in MagazineIssueVersionFiles.query.all() if file.magazine_issue_version.magazine_issue.magazine_id == self.id]

class BindingType(enum.Enum):
    glued = "GL"
    stapled = "ST"
    none = "NO"
    sewn = "SW"
    not_applicable = "NA"


class Periodicity(enum.Enum):
    weekly = "w"
    biweekly = "bw"
    monthly = "m"
    bimonthly = "bm"
    quarterly = "q"
    annually = "a"
    non_periodical = "np"

    @classmethod
    def choices(cls):
        return [(choice, choice.name) for choice in cls]

    @classmethod
    def coerce(cls, item):
        return cls(item) if not isinstance(item, cls) else item

    def __str__(self):
        return str(self.value)


class MagazineForm(enum.Enum):
    electronic = "ele"
    paper = "pap"
    CD = "CD"
    DVD = "DVD"
    diskette = "dis"


class IssueStatus(enum.Enum):
    have = "h"
    dont_have = "n"
    problems = "p"
    existence_unconfirmed = "e"


class MagazineIssue(HistoryTrait, CheckedTrait):
    __tablename__ = "magazine_issues"
    # for machine checking:
    #   issue_number+calendar_id for non-specials, else issue_title NOT NULL
    #   periodicity set
    #   at least year is set
    #   page_count set
    id = db.Column(db.Integer(), unique=True, primary_key=True)
    issue_number = db.Column(db.Integer(), nullable=True)
    calendar_id = db.Column(db.String(64), nullable=True)

    issue_title = db.Column(db.String(127), default="")
    current_magazine_name = db.Column(db.String(127))
    is_special_issue = db.Column(db.Boolean())

    periodicity = db.Column(db.Enum(Periodicity), nullable=True)

    published_day = db.Column(db.Integer(), nullable=True)
    published_month = db.Column(db.Integer(), nullable=True)
    published_year = db.Column(db.Integer(), nullable=True)

    page_count = db.Column(db.Integer(), nullable=True)
    circulation = db.Column(db.Integer(), nullable=True)

    chief_editor_id = db.Column(db.Integer, db.ForeignKey('parties.id'), nullable=True)

    issuer_id = db.Column(db.Integer(), db.ForeignKey("issuers.id"), nullable=True)
    issuer = db.relationship("Issuer")

    magazine_id = db.Column(db.Integer(), db.ForeignKey("magazines.id"), nullable=False)
    magazine = db.relationship("Magazine", backref="issues")

    note = db.Column(db.Text())

    __table_args__ = (
        UniqueConstraint('issue_number', 'magazine_id', name='_unique_issue'),
    )

    def __str__(self):
        issue_title = self.calendar_id if not self.is_special_issue else self.issue_title

        if issue_title is None or len(issue_title) == 0:
            issue_title = f"číslo {self.issue_number}"

        return f"{self.current_magazine_name}: { issue_title }"


class Currency(enum.Enum):
    CZK = "CZK"
    EUR = "EUR"
    CSK = "CSK"
    SK = "SK"
    PLN = "PLN"
    GBP = "GBP"


class Format(HistoryTrait):
    __tablename__ = "formats"
    id = db.Column(db.Integer(), unique=True, primary_key=True)
    binding_type = db.Column(db.Enum(BindingType), nullable=True)
    name = db.Column(db.String(127), default="")
    width = db.Column(db.Integer())
    height = db.Column(db.Integer())

    def __str__(self):
        return self.name

class MagDBFileType(enum.Enum):
    logo        = 10
    scan        = 11
    cover_page  = 12
    index_page  = 13
    photo       = 14

    @classmethod
    def choices(cls):
        return [(choice, choice.name) for choice in cls]

    @classmethod
    def coerce(cls, item):
        return cls(int(item)) if not isinstance(item, cls) else item

    def __str__(self):
        return str(self.value)


class MagazineIssueVersion(HistoryTrait, CheckedTrait):
    __tablename__ = "magazine_issue_versions"
    # for machine checking:
    #   form is set
    #   format is set
    #   confirmed is True
    id = db.Column(db.Integer(), unique=True, primary_key=True)
    magazine_issue_id = db.Column(db.Integer(), db.ForeignKey("magazine_issues.id"), nullable=False)
    magazine_issue = db.relationship("MagazineIssue", backref="versions")
    name_suffix = db.Column(db.String(127))

    form = db.Column(db.Enum(MagazineForm), nullable=True)

    format_id = db.Column(db.Integer(), db.ForeignKey("formats.id"), nullable=True)
    format = db.relationship("Format")

    confirmed = db.Column(db.Boolean())
    issn_or_isbn = db.Column(db.String(25), nullable=True)
    register_number_mccr = db.Column(db.String(), nullable=True)
    barcode = db.Column(db.String(15), nullable=True)
    status = db.Column(db.Enum(IssueStatus))

    note = db.Column(db.Text())

    def __str__(self):
        return f"{str(self.magazine_issue)} {self.name_suffix if self.name_suffix is not None else ''}"

    def get_logos(self):
        return [file for file in self.files if file.file_type == MagDBFileType.logo]


class MagazineIssueVersionPrice(HistoryTrait):
    __tablename__ = "magazine_issue_version_prices"
    id = db.Column(db.Integer(), unique=True, primary_key=True)

    issue_version_id = db.Column(db.Integer(), db.ForeignKey("magazine_issue_versions.id"))
    issue_version = db.relationship("MagazineIssueVersion", backref="prices")

    value = db.Column(db.Float())
    currency = db.Column(db.Enum(Currency))


class MagazineIssueVersionFiles(HistoryTrait):
    __tablename__ = "magazine_issue_files"
    id = db.Column(db.Integer(), unique=True, primary_key=True)

    magazine_issue_version_id = db.Column(db.Integer(), db.ForeignKey("magazine_issue_versions.id"), nullable=False)
    magazine_issue_version = db.relationship("MagazineIssueVersion", backref="files")

    file_id = db.Column(db.Integer(), db.ForeignKey("files.id"), nullable=False)
    file = db.relationship("File", backref="magazine_issue_files")

    file_type = db.Column(db.Enum(MagDBFileType))


class MagazineSupplement(HistoryTrait):
    __tablename__ = "magazine_supplement"
    id = db.Column(db.Integer(), unique=True, primary_key=True)
    title = db.Column(db.String(255), unique=True, info={"label": "Název přílohy"})
    note = db.Column(db.Text())
    status = db.Column(db.Enum(IssueStatus))
    confirmed = db.Column(db.Boolean())

class MagazineSupplementVersion(HistoryTrait):
    __tablename__ = "magazine_supplement_version"
    id = db.Column(db.Integer(), unique=True, primary_key=True)

    magazine_supplement_id = db.Column(db.Integer(), db.ForeignKey("magazine_supplement.id"), nullable=False)
    magazine_supplement = db.relationship("MagazineSupplement", backref="supplement_versions")

    magazine_issue_version_id = db.Column(db.Integer(), db.ForeignKey("magazine_issue_versions.id"), nullable=False)
    magazine_issue_version = db.relationship("MagazineIssueVersion", backref="supplements")


class MagazineSupplementVersionFiles(HistoryTrait):
    __tablename__ = "magazine_supplement_version_files"
    id = db.Column(db.Integer(), unique=True, primary_key=True)

    magazine_supplement_version_id = db.Column(db.Integer(), db.ForeignKey("magazine_supplement_version.id"), nullable=False)
    magazine_supplement_version = db.relationship("MagazineSupplementVersion", backref="supplement_files")

    file_id = db.Column(db.Integer(), db.ForeignKey("files.id"), nullable=False)
    file = db.relationship("File", backref="magazine_supplement_files")

    file_type = db.Column(db.Enum(MagDBFileType))
