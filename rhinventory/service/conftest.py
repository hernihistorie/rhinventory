from os import environ

from pytest import fixture
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_TEST_DATABASE_URL = environ.get("TEST_DATABASE_URL")


@fixture(scope="session")
def session_factory():
    try:
        engine = create_engine(
            SQLALCHEMY_TEST_DATABASE_URL
        )
    except KeyError:
        raise RuntimeError("No TEST_DATABASE_URL environment variable")

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    yield SessionLocal


@fixture(scope='function')
def test_db_session(session_factory):
    session = session_factory()
    transaction = session.begin()
    try:
        yield session
    finally:
        transaction.rollback()
        session.close()


