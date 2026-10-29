from pytest import fixture
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@fixture(scope="session")
def session_factory(database_url):
    engine = create_engine(database_url)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    yield SessionLocal

    engine.dispose()


@fixture(scope='function')
def test_db_session(session_factory):
    session = session_factory()
    transaction = session.begin()
    try:
        yield session
    finally:
        transaction.rollback()
        session.close()
