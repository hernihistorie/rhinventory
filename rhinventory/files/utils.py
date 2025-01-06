from flask import current_app
import os
from pathlib import Path

def get_dropzone_path() -> Path:
    # make path absolute
    return Path(os.path.abspath(current_app.config['DROPZONE_PATH']))

def get_dropzone_files() -> list[Path]:
    path = get_dropzone_path()
    return sorted([f for f in path.iterdir() if f.is_file()])
