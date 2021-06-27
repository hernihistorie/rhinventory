
import os
from environs import Env

env = Env()
env.read_env()

ENV = env.str('FLASK_ENV', default='production')
DEBUG = ENV == 'development'
SQLALCHEMY_DATABASE_URI = env.str('DATABASE_URL')
SECRET_KEY = env.str('SECRET_KEY')
DEBUG_TB_INTERCEPT_REDIRECTS = False

GITHUB_CLIENT_ID = env.str('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = env.str('GITHUB_CLIENT_SECRET')

FILES_DIR = os.path.abspath(env.str('FILES_DIR'))