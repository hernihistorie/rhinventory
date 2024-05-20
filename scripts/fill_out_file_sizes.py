import os.path
import tqdm

from rhinventory.app import create_app
from rhinventory.extensions import db
from rhinventory.db import File

app = create_app()

with app.app_context():
    files = db.session.query(File).filter(File.size == None).all()
    for file in tqdm.tqdm(files):
        try:
            size = os.path.getsize(file.full_filepath)
        except Exception:
            print(f"Warning: Failed to get size for {file.full_filepath}")
            continue
        
        file.size = size
        db.session.add(file)

    db.session.commit()