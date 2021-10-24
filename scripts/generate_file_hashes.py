import tqdm

from rhinventory.app import create_app
from rhinventory.extensions import db
from rhinventory.db import File

app = create_app()

with app.app_context():
    files = db.session.query(File).filter(File.md5 == None).all()
    for file in tqdm.tqdm(files):
        file.calculate_md5sum()

    db.session.commit()