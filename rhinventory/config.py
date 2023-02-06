import typing
import os
from environs import Env

env = Env()
env.read_env()

ENV: str = env.str('FLASK_ENV', default='production')
DEBUG: bool = ENV == 'development'
SQLALCHEMY_DATABASE_URI: str = env.str('DATABASE_URL')
SECRET_KEY: str = env.str('SECRET_KEY')
DEBUG_TB_INTERCEPT_REDIRECTS: bool = False

GITHUB_CLIENT_ID: str = env.str('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET: str = env.str('GITHUB_CLIENT_SECRET')
GITHUB_REDIRECT_URI: str = env.str('GITHUB_REDIRECT_URI')

FILE_STORE_LOCATIONS: typing.Dict[str, typing.Optional[str]] = {
    "local": os.path.abspath(env.str('FILE_STORE_LOCAL') or env.str('FILES_DIR')),
    "local_nas": os.path.abspath(env.str('FILE_STORE_LOCAL_NAS')) if 'FILE_STORE_LOCAL_NAS' in os.environ else None,
}

DEFAULT_FILE_STORE: str = env.str('DEFAULT_FILE_STORE', default='local')
assert DEFAULT_FILE_STORE in FILE_STORE_LOCATIONS, f"Invalid DEFAULT_FILE_STORE: {DEFAULT_FILE_STORE}"

MULTIPROCESSING_ENABLED: bool = env.bool("MULTIPROCESSING_ENABLED")
