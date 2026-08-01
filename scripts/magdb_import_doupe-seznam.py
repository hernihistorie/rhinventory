"""
Import ``data/doupe-seznam.xlsx`` into the MagDB tables.

The importer is designed to be idemportent.
"""
import argparse
import re
from pathlib import Path
from typing import TypedDict, cast

import openpyxl

from rhinventory.app import create_app
from rhinventory.extensions import db
from rhinventory.models.magdb import (
    BARCODE_MAX_LEN,
    Format,
    Magazine,
    MagazineForm,
    MagazineIssue,
    MagazineIssueVersion,
    MagazineIssueVersionPrice,
    Periodicity,
)

DEFAULT_XLSX_PATH = Path(__file__).resolve().parent.parent / "data" / "doupe-seznam.xlsx"

DEFAULT_FORM = MagazineForm.paper


# One spreadsheet row, keyed by normalized (lower-cased, single-spaced) header.
# Cells that are blank for special issues are typed Optional; the rest are always
# present. Values are whatever openpyxl yields (numbers as int, text as str).
MagazineRow = TypedDict(
    "MagazineRow",
    {
        "magazine": str,
        "issue number": int | str,  # '7+8' doubles and 'speciál …' come through as str
        "published year": int,
        "published month": int,
        "calendar id": str | None,  # None for special issues
        "periodicity": str | None,  # None for special issues
        "page count": int,
        "format": str,
        "name suffix": str,
        "price": str,
        "barcode": str,
        "issn or isbn": str,
        "register number mccr": str,
    },
)


def norm_header(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def read_rows(path: Path) -> list[MagazineRow]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    assert rows

    header = [norm_header(c) for c in rows[0]]
    missing = set(MagazineRow.__annotations__) - set(header)
    if missing:
        raise ValueError(f"Spreadsheet is missing expected column(s): {sorted(missing)}")

    result: list[MagazineRow] = []
    for raw in rows[1:]:
        row = {header[i]: raw[i] for i in range(len(header))}
        # Skip fully-empty trailing rows.
        if all(v is None or str(v).strip() == "" for v in row.values()):
            continue
        result.append(cast(MagazineRow, row))
    return result


def normalize_barcode(value):
    """Strip whitespace from a barcode; drop (with a warning) if it still won't fit."""
    normalized = re.sub(r"\s+", "", str(value))
    if len(normalized) > BARCODE_MAX_LEN:
        print(f"    ! barcode {value!r} is {len(normalized)} chars (> {BARCODE_MAX_LEN}), leaving empty")
        return None
    return normalized


def apply_fields(obj, **fields) -> bool:
    """Set attributes that differ; return True if anything changed."""
    changed = False
    for key, val in fields.items():
        if getattr(obj, key) != val:
            setattr(obj, key, val)
            changed = True
    return changed


class Stats:
    def __init__(self):
        self.created = 0
        self.updated = 0

    def note(self, was_created: bool, changed: bool):
        if was_created:
            self.created += 1
        elif changed:
            self.updated += 1


def upsert_issue(magazine: Magazine, row: MagazineRow) -> tuple[MagazineIssue, bool, bool]:
    calendar_id = row["calendar id"]
    number_cell = row["issue number"]
    is_special = calendar_id is None

    # Only plain numeric issues get a number; '7+8' doubles and specials are str -> None.
    issue_number = number_cell if isinstance(number_cell, int) else None
    issue_title = str(number_cell) if (is_special and number_cell is not None) else ""

    periodicity = row["periodicity"]  # None for special issues

    if is_special:
        issue = (
            MagazineIssue.query.filter_by(magazine_id=magazine.id, issue_title=issue_title)
            .filter(MagazineIssue.calendar_id.is_(None))
            .one_or_none()
        )
    else:
        issue = MagazineIssue.query.filter_by(
            magazine_id=magazine.id, calendar_id=calendar_id
        ).one_or_none()

    created = issue is None
    if created:
        issue = MagazineIssue(magazine_id=magazine.id)
        db.session.add(issue)

    changed = apply_fields(
        issue,
        issue_number=issue_number,
        calendar_id=calendar_id,
        issue_title=issue_title,
        current_magazine_name=magazine.title,
        is_special_issue=is_special,
        periodicity=Periodicity[periodicity.lower()] if periodicity else None,
        published_year=row["published year"],
        published_month=row["published month"],
        page_count=row["page count"],
    )
    db.session.flush()
    return issue, created, changed


def upsert_version(
    issue: MagazineIssue, fmt: Format | None, row: MagazineRow
) -> tuple[MagazineIssueVersion, bool, bool]:
    name_suffix = row["name suffix"] or ""

    version = MagazineIssueVersion.query.filter_by(
        magazine_issue_id=issue.id, name_suffix=name_suffix
    ).one_or_none()

    created = version is None
    if created:
        version = MagazineIssueVersion(
            magazine_issue_id=issue.id,
            name_suffix=name_suffix,
            inserted=True,  # created by the importer, not hand-entered
            manually_checked=False,
        )
        db.session.add(version)

    changed = apply_fields(
        version,
        form=DEFAULT_FORM,
        format_id=fmt.id if fmt else None,
        confirmed=True,
        status=None,  # spreadsheet carries no possession status
        issn_or_isbn=row.get("issn or isbn"),
        register_number_mccr=row.get("register number mccr"),
        barcode=normalize_barcode(row.get("barcode")),
    )
    db.session.flush()
    return version, created, changed


def run(path: Path, dry_run: bool):
    rows = read_rows(path)
    print(f"Read {len(rows)} data row(s) from {path}")

    stats = {name: Stats() for name in ("magazine", "format", "issue", "version", "price")}

    for i, row in enumerate(rows, start=1):
        magazine_title = row.get("magazine")
        if not magazine_title:
            print(f"  row {i}: no magazine name, skipping")
            continue

        magazine, mag_created = Magazine.get_or_create(magazine_title)
        stats["magazine"].note(mag_created, False)

        fmt, *fmt_flags = Format.get_or_create(Format.from_string(row.get("format")))
        stats["format"].note(*fmt_flags)

        issue, *issue_flags = upsert_issue(magazine, row)
        stats["issue"].note(*issue_flags)

        version, *version_flags = upsert_version(issue, fmt, row)
        stats["version"].note(*version_flags)

        _, *price_flags = MagazineIssueVersionPrice.get_or_create(
            version, MagazineIssueVersionPrice.from_string(row.get("price"))
        )
        stats["price"].note(*price_flags)

    if dry_run:
        db.session.rollback()
        print("\nDRY RUN — rolled back, nothing was written.")
    else:
        db.session.commit()
        print("\nCommitted.")

    print("\nSummary (created / updated):")
    for name, s in stats.items():
        print(f"  {name:9s}: {s.created:3d} created, {s.updated:3d} updated")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_XLSX_PATH, help="Path to the .xlsx file")
    parser.add_argument(
        "--dry-run", action="store_true", help="Parse and process but roll back instead of committing"
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        run(args.file, args.dry_run)


if __name__ == "__main__":
    main()
