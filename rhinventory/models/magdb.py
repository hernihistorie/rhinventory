import enum
import re
from typing import TYPE_CHECKING

import flask_login
from sqlalchemy import UniqueConstraint, func

from rhinventory.extensions import db
from rhinventory.models.user import User
from rhinventory.util import slugify

if TYPE_CHECKING:
    from rhinventory.models.file import File


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
    slug = db.Column(db.String(255), unique=True)
    title = db.Column(db.String(255), unique=True, info={"label": "Název časopisu"})
    description = db.Column(db.Text(), default=None, info={"label": "Popis"})
    description_en = db.Column(db.Text(), default=None)
    blurb_cs = db.Column(db.Text(), default=None)
    blurb_en = db.Column(db.Text(), default=None)
    country_id = db.Column(db.Integer, db.ForeignKey('countries.id'), nullable=True)

    url_archive_org = db.Column(db.String(), nullable=True)
    url_oldgames_sk = db.Column(db.String(), nullable=True)
    url_ndk_cz = db.Column(db.String(), nullable=True)
    url_dikda_sk = db.Column(db.String(), nullable=True)
    url_level_archiv = db.Column(db.String(), nullable=True)
    url_wikipedia_cs = db.Column(db.String(), nullable=True)
    url_wikipedia_en = db.Column(db.String(), nullable=True)
    url_wikidata = db.Column(db.String(), nullable=True)
    url_arbitrary = db.Column(db.String(), nullable=True)
    url_arbitrary_title = db.Column(db.String(), nullable=True)

    url_issue_scan_template = db.Column(db.String(), nullable=True)

    def __str__(self):
        return self.title

    @classmethod
    def get_or_create(cls, title: str) -> tuple["Magazine", bool]:
        """Find a magazine by title, or create one (with a slug). Returns (magazine, created)."""
        magazine = cls.query.filter_by(title=title).one_or_none()
        if magazine is not None:
            return magazine, False
        magazine = cls(title=title, slug=slugify(title))
        db.session.add(magazine)
        db.session.flush()
        return magazine, True

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
    
    scan_url = db.Column(db.String(), nullable=True)

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

    def __str__(self):
        return str(self.name)


class Format(HistoryTrait):
    __tablename__ = "formats"
    id = db.Column(db.Integer(), unique=True, primary_key=True)
    binding_type = db.Column(db.Enum(BindingType), nullable=True)
    name = db.Column(db.String(127), default="")
    width = db.Column(db.Integer())
    height = db.Column(db.Integer())

    def __str__(self):
        return self.name

    @classmethod
    def from_string(cls, value: str | None) -> "Format | None":
        """Parse '200x270 stapled' into a transient (unsaved) Format."""
        if value is None or not str(value).strip():
            return None
        value = str(value).strip()

        binding = None
        dims_part = value
        for word in value.split():
            try:
                binding = BindingType[word.lower()]
                dims_part = value.replace(word, "").strip()
                break
            except KeyError:
                continue

        match = re.search(r"(\d+)\s*[x×]\s*(\d+)", dims_part)
        if not match:
            raise ValueError(f"Cannot parse format dimensions: {value!r}")
        width, height = int(match.group(1)), int(match.group(2))
        return cls(width=width, height=height, binding_type=binding, name=value)

    @classmethod
    def get_or_create(cls, template: "Format | None") -> tuple["Format | None", bool, bool]:
        """Find a format matching ``template``'s dimensions and binding, or persist the
        template as a new one. Returns (format, created, changed)."""
        if template is None:
            return None, False, False

        existing = cls.query.filter_by(
            width=template.width, height=template.height, binding_type=template.binding_type
        ).one_or_none()
        if existing is None:
            db.session.add(template)
            db.session.flush()
            return template, True, False

        changed = bool(template.name) and existing.name != template.name
        if changed:
            existing.name = template.name
        db.session.flush()
        return existing, False, changed


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

BARCODE_MAX_LEN = 15

class MagazineIssueVersion(HistoryTrait, CheckedTrait):
    __tablename__ = "magazine_issue_versions"
    # for machine checking:
    #   form is set
    #   format is set
    #   confirmed is True
    id = db.Column(db.Integer(), unique=True, primary_key=True)
    magazine_issue_id = db.Column(db.Integer(), db.ForeignKey("magazine_issues.id"), nullable=False)
    magazine_issue = db.relationship(
        "MagazineIssue", backref=db.backref("versions", order_by="MagazineIssueVersion.name_suffix")
    )
    name_suffix = db.Column(db.String(127))

    form = db.Column(db.Enum(MagazineForm), nullable=True)

    format_id = db.Column(db.Integer(), db.ForeignKey("formats.id"), nullable=True)
    format = db.relationship("Format")

    confirmed = db.Column(db.Boolean())
    issn_or_isbn = db.Column(db.String(25), nullable=True)
    register_number_mccr = db.Column(db.String(), nullable=True)
    barcode = db.Column(db.String(BARCODE_MAX_LEN), nullable=True)
    status = db.Column(db.Enum(IssueStatus))

    note = db.Column(db.Text())

    def __str__(self):
        return f"{str(self.magazine_issue)} {self.name_suffix if self.name_suffix is not None else ''}"

    def get_logos(self):
        return [file for file in self.files if file.file_type == MagDBFileType.logo]

    def files_of_type(self, file_type: MagDBFileType) -> list["File"]:
        """The distinct files of one type attached to this version."""
        files = []
        for association in self.files:
            if association.file_type == file_type and association.file not in files:
                files.append(association.file)
        return files

    @property
    def cover_pages(self) -> list["File"]:
        return self.files_of_type(MagDBFileType.cover_page)

    @property
    def index_pages(self) -> list["File"]:
        return self.files_of_type(MagDBFileType.index_page)

    @property
    def prices_sorted(self) -> list["MagazineIssueVersionPrice"]:
        """Fully filled in prices, ordered by currency."""
        return sorted(
            (price for price in self.prices if price.value is not None and price.currency is not None),
            key=lambda price: price.currency.name,
        )


class MagazineIssueVersionPrice(HistoryTrait):
    __tablename__ = "magazine_issue_version_prices"
    id = db.Column(db.Integer(), unique=True, primary_key=True)

    issue_version_id = db.Column(db.Integer(), db.ForeignKey("magazine_issue_versions.id"))
    issue_version = db.relationship("MagazineIssueVersion", backref="prices")

    value = db.Column(db.Float())
    currency = db.Column(db.Enum(Currency))

    def __str__(self):
        return f"{self.value} {self.currency} (ID {self.id})"

    @classmethod
    def from_string(cls, value: str | None) -> "MagazineIssueVersionPrice | None":
        """Parse '99,90 CZK' into a transient (unsaved) price."""
        if value is None or not str(value).strip():
            return None
        match = re.match(r"^\s*([\d.,]+)\s*([A-Za-z]+)\s*$", str(value))
        if not match:
            raise ValueError(f"Cannot parse price: {value!r}")
        amount = float(match.group(1).replace(" ", "").replace(",", "."))
        try:
            currency = Currency[match.group(2).upper()]
        except KeyError:
            raise ValueError(f"Unknown currency in price: {value!r}")
        return cls(value=amount, currency=currency)

    @classmethod
    def get_or_create(
        cls, issue_version: "MagazineIssueVersion", template: "MagazineIssueVersionPrice | None"
    ) -> tuple["MagazineIssueVersionPrice | None", bool, bool]:
        """Find this version's price in ``template``'s currency, or persist the template.
        Returns (price, created, changed)."""
        if template is None:
            return None, False, False

        existing = cls.query.filter_by(
            issue_version_id=issue_version.id, currency=template.currency
        ).one_or_none()
        if existing is None:
            template.issue_version_id = issue_version.id
            db.session.add(template)
            db.session.flush()
            return template, True, False

        changed = existing.value != template.value
        if changed:
            existing.value = template.value
        db.session.flush()
        return existing, False, changed


class MagazineIssueVersionFiles(HistoryTrait):
    __tablename__ = "magazine_issue_files"
    id = db.Column(db.Integer(), unique=True, primary_key=True)

    magazine_issue_version_id = db.Column(db.Integer(), db.ForeignKey("magazine_issue_versions.id"), nullable=False)
    magazine_issue_version = db.relationship("MagazineIssueVersion", backref="files")

    file_id = db.Column(db.Integer(), db.ForeignKey("files.id"), nullable=False)
    file = db.relationship("File", backref="magazine_issue_files")

    file_type = db.Column(db.Enum(MagDBFileType))

    def __str__(self):
        return f"{self.file_type.name} - {self.file.filename} (ID {self.id})"


class MagazineSupplement(HistoryTrait):
    __tablename__ = "magazine_supplement"
    id = db.Column(db.Integer(), unique=True, primary_key=True)
    title = db.Column(db.String(255), info={"label": "Název přílohy"})
    note = db.Column(db.Text())
    status = db.Column(db.Enum(IssueStatus))
    confirmed = db.Column(db.Boolean())

    def __str__(self):
        return f"{self.title}"

class MagazineSupplementVersion(HistoryTrait):
    __tablename__ = "magazine_supplement_version"
    id = db.Column(db.Integer(), unique=True, primary_key=True)

    magazine_supplement_id = db.Column(db.Integer(), db.ForeignKey("magazine_supplement.id"), nullable=False)
    magazine_supplement = db.relationship("MagazineSupplement", backref="supplement_versions")

    magazine_issue_version_id = db.Column(db.Integer(), db.ForeignKey("magazine_issue_versions.id"), nullable=False)
    magazine_issue_version = db.relationship("MagazineIssueVersion", backref="supplements")

    def __str__(self):
        return f"{str(self.magazine_issue_version)}: {self.magazine_supplement.title}"


class MagazineSupplementVersionFiles(HistoryTrait):
    __tablename__ = "magazine_supplement_version_files"
    id = db.Column(db.Integer(), unique=True, primary_key=True)

    magazine_supplement_version_id = db.Column(db.Integer(), db.ForeignKey("magazine_supplement_version.id"), nullable=False)
    magazine_supplement_version = db.relationship("MagazineSupplementVersion", backref="supplement_files")

    file_id = db.Column(db.Integer(), db.ForeignKey("files.id"), nullable=False)
    file = db.relationship("File", backref="magazine_supplement_files")

    file_type = db.Column(db.Enum(MagDBFileType))
