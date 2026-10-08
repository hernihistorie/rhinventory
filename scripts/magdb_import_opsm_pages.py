"""
Import OPSM cover and index page scans into MagDB.

Expects files named like ``OPSM_12_1999-04-p1.jpg`` (cover) and
``OPSM_12_1999-04-p4-5.jpg`` (index pages), plus ``OPSM_Top-Secret-Special-p1.jpg``
for the special issue. Run ``magdb_import_doupe-seznam.py`` first so the issues exist.

The importer is designed to be idempotent: files already uploaded (by checksum) are
reused, and only missing links are added.
"""
import argparse
import re
import shutil
import tempfile
from pathlib import Path

from tqdm import tqdm

from rhinventory.admin_views.file import DuplicateFile, upload_file
from rhinventory.app import create_app
from rhinventory.extensions import db
from rhinventory.models.enums import Privacy
from rhinventory.models.file import File, FileCategory
from rhinventory.models.magdb import (
    Magazine,
    MagazineIssue,
    MagazineIssueVersion,
    MagazineIssueVersionFiles,
    MagDBFileType,
)
from rhinventory.models.user import User

DEFAULT_DIR = Path(__file__).resolve().parent.parent.parent / "rhinventory_data" / "opsm-titulky-a-obsahy"

MAGAZINE_TITLE = "OPSM"

FILENAME_RE = re.compile(r"^OPSM_(?:(?P<number>\d+)_[^-]+-[^-]+|(?P<special>[A-Za-z-]+))-p(?P<pages>[\d-]+)\.jpe?g$", re.I)

# Special issues are keyed by the name used in the filename -> MagazineIssue.issue_title
SPECIAL_ISSUE_TITLES = {
    "Top-Secret-Special": "Top Secret Special",
}

FILE_TYPE_CATEGORIES = {
    MagDBFileType.cover_page: FileCategory.cover_page,
    MagDBFileType.index_page: FileCategory.index_page,
}


def parse_filename(name: str) -> tuple[int | str, MagDBFileType] | None:
    """Return (issue number or special issue title, file type), or None if unrecognized."""
    match = FILENAME_RE.match(name)
    if not match:
        return None
    file_type = MagDBFileType.cover_page if match["pages"] == "1" else MagDBFileType.index_page
    if match["number"]:
        return int(match["number"]), file_type
    title = SPECIAL_ISSUE_TITLES.get(match["special"])
    if title is None:
        return None
    return title, file_type


def find_version(magazine: Magazine, key: int | str) -> MagazineIssueVersion | None:
    query = MagazineIssue.query.filter_by(magazine_id=magazine.id)
    if isinstance(key, int):
        query = query.filter_by(issue_number=key, is_special_issue=False)
    else:
        query = query.filter_by(issue_title=key, is_special_issue=True)
    issue = query.one_or_none()
    if issue is None:
        return None

    versions = MagazineIssueVersion.query.filter_by(magazine_issue_id=issue.id).all()
    if len(versions) != 1:
        raise ValueError(f"Expected exactly one version of {issue}, found {len(versions)}")
    return versions[0]


def upload_or_reuse(path: Path, category: FileCategory, user: User) -> tuple[File, bool]:
    """Upload a copy of ``path`` (upload_file moves its input); reuse an identical existing file."""
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / path.name
        shutil.copy2(path, copy)
        try:
            file = upload_file(copy, category=category, privacy=Privacy.public, user=user)
        except DuplicateFile as e:
            return e.matching_file, False

    db.session.add(file)
    db.session.flush()
    file.make_thumbnail()
    return file, True


def run(directory: Path, username: str, dry_run: bool):
    user = User.query.filter((User.username == username) | (User.github_login == username)).first()
    if user is None:
        raise SystemExit(f"No user with username or GitHub login {username!r}")

    magazine = Magazine.query.filter_by(title=MAGAZINE_TITLE).one_or_none()
    if magazine is None:
        raise SystemExit(f"Magazine {MAGAZINE_TITLE!r} not found; import the spreadsheet first")

    paths = sorted(p for p in directory.iterdir() if p.is_file())
    print(f"Found {len(paths)} file(s) in {directory}")

    uploaded = reused = linked = skipped = 0
    for path in tqdm(paths, desc="Processing files"):
        parsed = parse_filename(path.name)
        if parsed is None:
            print(f"  {path.name}: unrecognized filename, skipping")
            skipped += 1
            continue
        key, file_type = parsed

        version = find_version(magazine, key)
        if version is None:
            print(f"  {path.name}: no issue {key!r} in MagDB, skipping")
            skipped += 1
            continue

        if dry_run:
            print(f"  {path.name}: {file_type.name} -> {version.magazine_issue}")
            continue

        file, was_uploaded = upload_or_reuse(path, FILE_TYPE_CATEGORIES[file_type], user)
        if was_uploaded:
            uploaded += 1
        else:
            reused += 1

        link = MagazineIssueVersionFiles.query.filter_by(
            magazine_issue_version_id=version.id, file_id=file.id, file_type=file_type
        ).one_or_none()
        if link is None:
            db.session.add(
                MagazineIssueVersionFiles(magazine_issue_version_id=version.id, file_id=file.id, file_type=file_type)
            )
            linked += 1

        # Commit per file: upload_file has already written to the file store.
        db.session.commit()

    if dry_run:
        print("\nDRY RUN — nothing was uploaded or written.")
    print(f"\nSummary: {uploaded} uploaded, {reused} already uploaded, {linked} linked, {skipped} skipped")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="Directory with the scans")
    parser.add_argument("--user", required=True, help="Username or GitHub login to record as the uploader")
    parser.add_argument(
        "--dry-run", action="store_true", help="Only show how files map to issues; upload nothing"
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        run(args.dir, args.user, args.dry_run)


if __name__ == "__main__":
    main()
