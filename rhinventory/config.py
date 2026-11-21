import typing
import os
from environs import Env

env = Env()
env.read_env()

ENV: str = env.str('FLASK_ENV', default='production')
DEBUG: bool = ENV == 'development'
SQLALCHEMY_RECORD_QUERIES = DEBUG
SQLALCHEMY_DATABASE_URI: str = env.str('DATABASE_URL')
SECRET_KEY: str = env.str('SECRET_KEY')
DEBUG_TB_INTERCEPT_REDIRECTS: bool = False

GITHUB_CLIENT_ID: str = env.str('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET: str = env.str('GITHUB_CLIENT_SECRET')
FILE_STORE_LOCAL_NAS: str | None = env.str('FILE_STORE_LOCAL_NAS', default=None)
FILE_STORE_CORUSCANT: str | None = env.str('FILE_STORE_CORUSCANT', default=None)

FILE_STORE_LOCATIONS: dict[str, str | None] = {
    "local": os.path.abspath(env.str('FILE_STORE_LOCAL') or env.str('FILES_DIR')),
    "local_nas": os.path.abspath(FILE_STORE_LOCAL_NAS) if FILE_STORE_LOCAL_NAS else None,
    "coruscant": os.path.abspath(FILE_STORE_CORUSCANT) if FILE_STORE_CORUSCANT else None,
}

DEFAULT_FILE_STORE: str = env.str('DEFAULT_FILE_STORE', default='local')
assert DEFAULT_FILE_STORE in FILE_STORE_LOCATIONS, f"Invalid DEFAULT_FILE_STORE: {DEFAULT_FILE_STORE}"

# File stores nginx serves itself, mapped to the internal location it serves each one at,
# e.g. `local=/_files/local/,coruscant=/_files/coruscant/` (see "Serving files" in README.md).
# Files in other stores are sent by Flask.
X_ACCEL_REDIRECT_LOCATIONS: dict[str, str] = env.dict('X_ACCEL_REDIRECT_LOCATIONS', default={})
for _store in X_ACCEL_REDIRECT_LOCATIONS:
    assert _store in FILE_STORE_LOCATIONS, f"Invalid file store in X_ACCEL_REDIRECT_LOCATIONS: {_store}"

DROPZONE_PATH: str = env.str('DROPZONE_PATH', default='dropzone')

MULTIPROCESSING_ENABLED: bool = env.bool("MULTIPROCESSING_ENABLED")

SENTRY_DSN = env.str('SENTRY_DSN', None)

# Where herniarchiv.cz shows rhinventory, e.g. https://herniarchiv.cz/inventory.  When set,
# visitors who aren't logged in are redirected there (see "Embedding" in README.md).
HAWEB_INVENTORY_URL: str | None = env.str('HAWEB_INVENTORY_URL', default=None)
