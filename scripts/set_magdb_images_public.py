import tqdm

from rhinventory.app import create_app
from rhinventory.extensions import db
from rhinventory.models.enums import Privacy
from rhinventory.models.file import File
from rhinventory.models.magdb import MagazineIssueVersionFiles

app = create_app()

with app.app_context():
    magazine_issue_version_file: list[MagazineIssueVersionFiles] = db.session.query(MagazineIssueVersionFiles).all()
    for magdb_file in tqdm.tqdm(magazine_issue_version_file):
        file: File | None = magdb_file.file
        if file:
            file.privacy = Privacy.public
            db.session.add(file)

    db.session.commit()
