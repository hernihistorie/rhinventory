from sqlalchemy import text


def test_db_running(test_db_session):
    """Test whether testing DB is running."""
    assert test_db_session.execute(text('SELECT 1'))
